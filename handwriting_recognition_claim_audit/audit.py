"""Deterministic documentation and Python source inspection."""
import argparse
import ast
import json
from pathlib import Path
import re
import sys

from . import __version__
from .phrases import HANDWRITINGRECOGNITION, NOHANDWRITINGRECOGNITION, GENERIC_NAMES

SKIP = {'.git', '__pycache__', '.venv', 'venv', 'env', '.env', 'dist', 'build'}
POSITIVE = 'documented-handwriting-recognition-claim-false'
NEGATIVE = 'documented-no-handwriting-recognition-claim-false'


def matches(text, phrases):
    text = text.lower()
    found = []
    for phrase in sorted(phrases, key=len, reverse=True):
        start = text.find(phrase)
        while start >= 0:
            found.append(phrase)
            text = text[:start] + ' ' * len(phrase) + text[start + len(phrase):]
            start = text.find(phrase)
    return found, text


def prose(text):
    return re.sub(r'^\s*```[^\n]*\n.*?^\s*```[^\n]*(?:\n|$)', '', text,
                  flags=re.M | re.S).replace('`', '')


def evidence(source):
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    nodes = list(ast.walk(tree))
    shadow = {n.name for n in nodes if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
    imports = {}
    from_imports = set()
    for n in nodes:
        if isinstance(n, ast.Import):
            for a in n.names:
                imports[a.asname or a.name.split('.')[0]] = a.name if a.asname else a.name.split('.')[0]
        elif isinstance(n, ast.ImportFrom):
            for a in n.names:
                imports[a.asname or a.name] = (n.module or '') + '.' + a.name
                from_imports.add(a.asname or a.name)

    def resolve(n):
        if isinstance(n, ast.Name):
            return '' if n.id in shadow else imports.get(n.id, '')
        if isinstance(n, ast.Attribute):
            base = resolve(n.value)
            return base + '.' + n.attr if base and n.attr not in shadow else ''
        return ''

    instances = {}

    def literal(n):
        return n.value if isinstance(n, ast.Constant) and isinstance(n.value, str) else ''

    def value_kind(n):
        if isinstance(n, ast.Name):
            return '' if n.id in shadow else instances.get(n.id, '')
        if not isinstance(n, ast.Call):
            return ''
        name = resolve(n.func)
        if name.endswith('.from_pretrained'):
            name = name.rsplit('.', 1)[0]
        for factory, kind in (('TrOCRProcessor', 'processor'),
                              ('VisionEncoderDecoderModel', 'trocr'),
                              ('AutoModelForVision2Seq', 'vision')):
            if name == 'transformers.' + factory:
                return kind
        if name == 'transformers.pipeline':
            keywords = {k.arg: k.value for k in n.keywords}
            task = literal(n.args[0]) if n.args else literal(keywords.get('task'))
            model = literal(keywords.get('model')) if 'model' in keywords else (literal(n.args[1]) if len(n.args) > 1 else '')
            if task == 'image-to-text' and 'trocr' in model.lower():
                return 'pipeline'
        return ''

    # Propagate simple assigned instance aliases within this module only.
    for _ in range(len(nodes) + 1):
        before = dict(instances)
        for n in nodes:
            if isinstance(n, (ast.Assign, ast.AnnAssign)):
                kind = value_kind(n.value)
                if kind:
                    targets = n.targets if isinstance(n, ast.Assign) else [n.target]
                    for target in targets:
                        if isinstance(target, ast.Name):
                            instances[target.id] = kind
        if before == instances:
            break
    processor = any(value_kind(n) == 'processor' for n in nodes if isinstance(n, ast.Call))
    trocr_run = False
    calls = []
    for n in nodes:
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        name = resolve(f)
        calls.append(name)
        if isinstance(f, ast.Attribute):
            if f.attr in GENERIC_NAMES and f.attr not in shadow and not (isinstance(f.value, ast.Name) and f.value.id in shadow):
                return True
            kind = value_kind(f.value)
            if f.attr == 'generate' and f.attr not in shadow:
                if kind == 'vision':
                    return True
                if kind == 'trocr':
                    trocr_run = True
        elif (isinstance(f, ast.Name) and f.id in from_imports
              and name.rsplit('.', 1)[-1] in GENERIC_NAMES):
            return True
        if value_kind(f) in ('vision', 'pipeline'):
            return True
    def kraken(suffix):
        return any(name.startswith('kraken.') and name.rsplit('.', 1)[-1] == suffix for name in calls)
    return (processor and trocr_run) or (kraken('load_any') and kraken('rpred'))


def audit(repo, ignore=(), verbose=False):
    root = Path(repo)
    if not root.is_dir():
        raise OSError('Repository is not a directory: ' + str(root))
    paths = []
    for p in sorted(root.rglob('*')):
        rel = p.relative_to(root).as_posix()
        if any(part in SKIP for part in p.relative_to(root).parts) or any(rel.startswith(prefix) for prefix in ignore):
            continue
        if any((parent / 'pyvenv.cfg').is_file() for parent in p.parents if parent != root and root in parent.parents):
            continue
        if p.is_file():
            paths.append((p, rel))
    has_evidence = False
    docs = []
    for p, rel in paths:
        if p.suffix == '.py':
            found = evidence(p.read_text(encoding='utf-8'))
            has_evidence |= found
            if verbose:
                print('source ' + rel + ': ' + ('evidence' if found else 'no evidence'), file=sys.stderr)
        parts = Path(rel).parts
        if rel == 'README.md' or (parts[0] == 'docs' and p.suffix == '.md') or 'tests' in parts:
            text = prose(p.read_text(encoding='utf-8'))
            denials, remaining = matches(text, NOHANDWRITINGRECOGNITION)
            claims, _ = matches(remaining, HANDWRITINGRECOGNITION)
            docs.append((rel, claims, denials, 'tests' in parts))
            if verbose:
                print('documentation ' + rel + ': ' + str(len(claims)) + ' claims, ' + str(len(denials)) + ' denials', file=sys.stderr)
    findings = []
    for rel, claims, denials, test in docs:
        for phrases, contradicted, identifier in ((claims, not has_evidence, POSITIVE), (denials, has_evidence, NEGATIVE)):
            if contradicted and phrases:
                severity = 'MEDIUM' if test else 'HIGH'
                findings.append(dict(id=identifier, severity=severity, path=rel, verdict='FAIL',
                                     message='Documentation and detected implementation disagree.', phrases=phrases))
    return findings


class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(1, 'error: ' + message + '\n')


def main(argv=None):
    parser = Parser(description='Audit documentation claims against Python source.')
    parser.add_argument('--version', action='version', version=__version__)
    sub = parser.add_subparsers(dest='command', required=True, parser_class=Parser)
    cmd = sub.add_parser('audit')
    cmd.add_argument('repo', nargs='?', default='.')
    cmd.add_argument('--json', action='store_true')
    cmd.add_argument('--verbose', action='store_true')
    cmd.add_argument('--ignore', action='append', default=[])
    cmd.add_argument('--fail-on', choices=['high', 'medium'], default='high')
    args = parser.parse_args(argv)
    try:
        if args.verbose:
            print('scope: ' + str(Path(args.repo).resolve()), file=sys.stderr)
        findings = audit(args.repo, args.ignore, args.verbose)
    except (OSError, UnicodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(findings))
    elif findings:
        for f in findings:
            print('{severity} {id} {path}: {message}'.format(**f))
    else:
        print('PASS')
    return 2 if any(f['severity'] == 'HIGH' or args.fail_on == 'medium' for f in findings) else 0
