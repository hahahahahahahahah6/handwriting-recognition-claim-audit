import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from handwriting_recognition_claim_audit.audit import audit, evidence, main, matches, HANDWRITINGRECOGNITION, NOHANDWRITINGRECOGNITION, GENERIC_NAMES

class AuditTests(unittest.TestCase):
    def test_phrase_oracle(self):
        self.assertEqual(list(HANDWRITINGRECOGNITION), ['handwriting recognition', 'handwriting-recognition', 'handwritten text recognition', 'handwritten-text recognition', 'recognizes handwriting', 'recognize handwriting', 'recognizing handwriting', 'recognized handwriting', 'recognize handwritten text', 'recognizes handwritten text', 'recognizing handwritten text', 'handwriting recognition support', 'supports handwriting recognition', 'handwriting recognition capability', 'handwriting recognition feature', 'handwriting recognition pipeline', 'handwriting recognition system', 'handwriting recognition tool', 'handwriting recognition framework', 'handwriting recognition library', 'handwriting recognition api', 'handwriting recognition model', 'handwriting recognition models', 'handwriting recognition engine', 'handwriting recognition module', 'handwriting recognition function', 'handwriting recognition functionality', 'handwriting recognition workflow', 'handwriting recognition method', 'handwriting recognition approach', 'handwriting recognition service', 'handwriting recognition results', 'handwriting recognition performance', 'handwriting recognition task', 'handwriting recognition tasks', 'handwriting recognition algorithm', 'handwriting recognition algorithms', 'handwriting recognition configuration', 'handwriting recognition script', 'read handwriting', 'reads handwriting', 'reading handwriting', 'transcribe handwriting', 'transcribes handwriting', 'transcribing handwriting', 'handwriting recognition mode', 'recognize handwritten notes', 'handwriting to text', 'handwriting-to-text', 'convert handwriting to text'])
        self.assertEqual(list(NOHANDWRITINGRECOGNITION), ['does not recognize handwriting', 'do not recognize handwriting', "doesn't recognize handwriting", "don't recognize handwriting", 'no handwriting recognition', 'without handwriting recognition', 'never recognizes handwriting', 'does not support handwriting recognition', 'handwriting recognition not supported', 'handwriting recognition unsupported', 'no handwriting recognition support', 'lacks handwriting recognition', 'missing handwriting recognition', 'handwriting recognition disabled', 'no handwriting recognition model', 'without handwriting recognition support', 'does not provide handwriting recognition', 'no automatic handwriting recognition', 'handwriting recognition not available', 'no handwriting recognition capability', 'does not recognize handwritten text', 'without a handwriting recognition model', 'does not perform handwriting recognition', 'never performs handwriting recognition'])

    def test_generic_oracle(self):
        self.assertEqual(list(GENERIC_NAMES), ['recognize_handwriting', 'recognize_handwritten_text', 'read_handwriting', 'transcribe_handwriting', 'recognize_handwritten', 'extract_handwriting', 'detect_handwriting', 'read_handwritten_text', 'transcribe_handwritten_text', 'recognize_handwritten_notes', 'decode_handwriting', 'parse_handwriting', 'convert_handwriting_to_text', 'handwriting_to_text', 'handwriting_recognition', 'recognize_cursive', 'read_cursive', 'transcribe_cursive', 'recognize_handwritten_characters', 'extract_handwritten_text', 'process_handwriting', 'analyze_handwriting', 'predict_handwriting', 'get_handwritten_text'])

    def fixture(self, readme='', code='', extra=None, flags=()):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'README.md').write_text(readme)
            (root/'app.py').write_text(code)
            for name, text in (extra or {}).items():
                p = root/name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(text)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                status = main(['audit', str(root)] + list(flags))
            return status, out.getvalue()

    def test_inventory_matching(self):
        for phrase in HANDWRITINGRECOGNITION:
            with self.subTest(phrase=phrase):
                self.assertEqual(matches(phrase, HANDWRITINGRECOGNITION)[0], [phrase])
        for phrase in NOHANDWRITINGRECOGNITION:
            with self.subTest(phrase=phrase):
                denials, rest = matches(phrase, NOHANDWRITINGRECOGNITION)
                self.assertEqual(denials, [phrase])
                self.assertEqual(matches(rest, HANDWRITINGRECOGNITION)[0], [])
        self.assertEqual(matches('convert handwriting to text', HANDWRITINGRECOGNITION)[0], ['convert handwriting to text'])

    def test_generics(self):
        for name in GENERIC_NAMES:
            for code in ('x.'+name+'()', 'from unknown import '+name+' as run; run()'):
                with self.subTest(code=code): self.assertTrue(evidence(code))

    def test_split_modules(self):
        self.assertEqual(self.fixture('handwriting recognition', 'from transformers import AutoModelForVision2Seq; m=AutoModelForVision2Seq()', {'other.py': 'm.generate(x)'})[0], 2)

    def test_matching(self):
        self.assertEqual(matches('handwriting recognition', HANDWRITINGRECOGNITION)[0], ['handwriting recognition'])
        self.assertEqual(self.fixture('does not recognize handwriting')[0], 0)
        self.assertEqual(self.fixture('HANDWRITING RECOGNITION')[0], 2)
        self.assertEqual(self.fixture('```text\nhandwriting recognition\n```')[0], 0)
        self.assertEqual(self.fixture('`handwriting recognition`')[0], 2)
        self.assertEqual(matches('she reads handwriting better than print', HANDWRITINGRECOGNITION)[0], ['reads handwriting'])

    def test_cli_good(self):
        self.assertEqual(self.fixture('handwriting recognition', 'x.recognize_handwriting()'), (0, 'PASS\n'))

    def test_cli_bad(self):
        status, out = self.fixture('handwriting recognition')
        self.assertEqual(status, 2)
        self.assertIn('HIGH documented-handwriting-recognition-claim-false', out)

    def test_cli_test_only(self):
        extra = {'tests/sample.md': 'handwriting recognition'}
        status, out = self.fixture(extra=extra)
        self.assertEqual(status, 0)
        self.assertIn('MEDIUM', out)
        self.assertEqual(self.fixture(extra=extra, flags=['--fail-on', 'medium'])[0], 2)

    def test_cli_denial(self):
        status, out = self.fixture('no handwriting recognition', 'x.recognize_handwriting()')
        self.assertEqual(status, 2)
        self.assertIn('HIGH documented-no-handwriting-recognition-claim-false', out)

    def test_cli_no_claim(self):
        self.assertEqual(self.fixture('A useful tool.'), (0, 'PASS\n'))

    def test_cli_json(self):
        status, out = self.fixture('handwriting recognition', flags=['--json'])
        f = json.loads(out)[0]
        self.assertEqual(status, 2)
        self.assertEqual(f['verdict'], 'FAIL')
        self.assertTrue(f['message'])

    def test_cli_ignore(self):
        self.assertEqual(self.fixture(extra={'docs/claim.md': 'handwriting recognition'}, flags=['--ignore', 'docs/'])[0], 0)

    def test_cli_version(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit) as cm:
            main(['--version'])
        self.assertEqual(cm.exception.code, 0)
        self.assertEqual(out.getvalue().strip(), '0.1.0')

    def test_readme(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(self.fixture((root/'README.md').read_text()), (0, 'PASS\n'))

    def test_io_and_usage(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(['audit', '/nonexistent-r142-directory']), 1)
            with self.assertRaises(SystemExit) as cm: main(['audit', '--unknown'])
        self.assertEqual(cm.exception.code, 1)

    def test_virtualenv_excluded(self):
        status, out = self.fixture('handwriting recognition', extra={
            'custom-env/pyvenv.cfg': 'home = /usr/bin',
            'custom-env/lib/model.py': 'x.recognize_handwriting()',
        })
        self.assertEqual(status, 2)

    def test_verbose(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(self.fixture(flags=['--verbose'])[0], 0)
        self.assertIn('scope:', err.getvalue())

    def test_transformer_routes(self):
        for factory in ('TrOCRProcessor', 'VisionEncoderDecoderModel', 'AutoModelForVision2Seq'):
            for setup, f in [(f'from transformers import {factory}; ', factory), (f'from transformers import {factory} as F; ', 'F'), ('import transformers as tf; ', 'tf.'+factory), ('import transformers; ', 'transformers.'+factory)]:
                for construction in (f+'()', f+'.from_pretrained("weights")'):
                    self.assertFalse(evidence(setup+construction))
                    if factory == 'TrOCRProcessor':
                        continue
                    processor = 'from transformers import TrOCRProcessor; TrOCRProcessor(); ' if factory == 'VisionEncoderDecoderModel' else ''
                    for expr in ('m='+construction+'; m.generate(x)', construction+'.generate(x)'):
                        with self.subTest(expr=expr, setup=setup):
                            self.assertTrue(evidence(processor+setup+expr))
                    if factory == 'AutoModelForVision2Seq':
                        self.assertTrue(evidence(setup+construction+'(x)'))
                        self.assertTrue(evidence(setup+'m='+construction+'; m(x)'))
                    else:
                        self.assertFalse(evidence(setup+construction+'.generate(x)'))
        self.assertFalse(evidence('from transformers import TrOCRProcessor, VisionEncoderDecoderModel\nclass TrOCRProcessor: pass\nTrOCRProcessor(); VisionEncoderDecoderModel().generate(x)'))

    def test_kraken(self):
        for setup, load, run in [('import kraken; ', 'kraken.lib.models.load_any', 'kraken.rpred.rpred'), ('from kraken.lib.models import load_any as L; from kraken.rpred import rpred as R; ', 'L', 'R')]:
            self.assertTrue(evidence(setup+load+'(); '+run+'()'))
            self.assertFalse(evidence(setup+load+'()'))
            self.assertFalse(evidence(setup+run+'()'))
        self.assertFalse(evidence('from kraken.lib.models import load_any\nfrom kraken.rpred import rpred\ndef load_any(): pass\nload_any(); rpred()'))

    def test_pipeline(self):
        for setup, f in [('from transformers import pipeline; ', 'pipeline'), ('from transformers import pipeline as P; ', 'P'), ('import transformers as tf; ', 'tf.pipeline')]:
            for args in ('"image-to-text", "microsoft/TROCR-base"', '"image-to-text", model="trocr-base"', 'task="image-to-text", model="trocr"'):
                self.assertTrue(evidence(setup+f+'('+args+')(x)'))
                self.assertTrue(evidence(setup+'p='+f+'('+args+'); p(x)'))
                self.assertFalse(evidence(setup+f+'('+args+')'))
            for task, model in [('image-to-text','caption-model'), ('image-classification','trocr'), ('object-detection','trocr'), ('text-classification','trocr')]:
                self.assertFalse(evidence(setup+f+'("'+task+'", model="'+model+'")(x)'))
        self.assertFalse(evidence('from transformers import pipeline\ndef pipeline(): pass\npipeline("image-to-text", model="trocr")(x)'))

    def test_rejections(self):
        cases = [
            'import transformers, trocr, kraken',
            'import pytesseract; pytesseract.image_to_string(x)',
            'import easyocr; r=easyocr.Reader(); r.readtext(x)',
            'from doctr.models import ocr_predictor; ocr_predictor()(x)',
            'from paddleocr import PaddleOCR; PaddleOCR()(x)',
            'from surya.recognition import RecognitionPredictor; RecognitionPredictor()(x)',
            'x.text_to_handwriting(text)', 'font.render(text)', 'x.verify_signature(x)',
            'from azure.ai.vision.imageanalysis import ImageAnalysisClient; c=ImageAnalysisClient(); c.analyze(x)',
            'from google.cloud.vision import ImageAnnotatorClient; c=ImageAnnotatorClient(); c.document_text_detection(x)',
            'import boto3; c=boto3.client("textract"); c.detect_document_text(x)',
            '"handwriting recognition recognize handwriting" # read handwriting',
            '"""recognize handwriting"""', 'recognize_handwriting()',
            'from unknown import recognize_handwriting; recognize_handwriting',
            'from unknown import recognize_handwriting\ndef recognize_handwriting(): pass\nrecognize_handwriting()',
            'from unknown import recognize_handwriting\nclass recognize_handwriting: pass\nrecognize_handwriting()',
            'import subprocess; subprocess.run(["recognition-cli", "page"])',
            'this is invalid python!',
        ]
        for code in cases:
            with self.subTest(code=code): self.assertFalse(evidence(code))

    def test_all_split_routes(self):
        for first, second in [
            ('from transformers import TrOCRProcessor, VisionEncoderDecoderModel; TrOCRProcessor(); m=VisionEncoderDecoderModel()', 'm.generate(x)'),
            ('from transformers import pipeline; p=pipeline("image-to-text", model="trocr")', 'p(x)'),
            ('from kraken.lib.models import load_any; load_any()', 'from kraken.rpred import rpred; rpred()'),
        ]:
            self.assertEqual(self.fixture('handwriting recognition', first, {'other.py':second})[0], 2)

if __name__ == '__main__':
    unittest.main()
