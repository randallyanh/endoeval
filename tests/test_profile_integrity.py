from __future__ import annotations
import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'src'))
from endoeval.contracts import EndoEvalError,load_authority,load_profile,safe_relative_path

class ProfileIntegrityTests(unittest.TestCase):
    def test_bundled_profile_and_input_boundary(self):
        profile=load_profile('endonerf-rgb-v1'); authority,_=load_authority(profile)
        self.assertEqual(profile['status'],'ready')
        self.assertEqual([len(s['frames']) for s in authority['scenes']],[20,8])
        self.assertEqual(sum(len(s['frames']) for s in authority['scenes']),28)
        self.assertEqual(authority['support']['definition'],'not(tool_mask > 0.5) AND not(invalid_mask > 0.5)')
        for scene in authority['scenes']:
            self.assertEqual(len({f['frame_id'] for f in scene['frames']}),len(scene['frames']))
            for frame in scene['frames']:
                for key in ('reference_sha256','tool_mask_sha256','invalid_mask_sha256'):
                    self.assertEqual(len(frame[key]),64)
        for bad in ('../outside','a\\b','/absolute','C:\\outside','a//b'):
            with self.assertRaises(EndoEvalError): safe_relative_path(bad,field='test')
if __name__=='__main__': unittest.main()
