from __future__ import annotations
import hashlib,json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
CLI=[sys.executable,'-B',str(ROOT/'endoeval.py')]

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def run(args,env,ok=True):
    p=subprocess.run(CLI+args,cwd=ROOT,env=env,text=True,capture_output=True)
    if ok and p.returncode!=0: raise AssertionError(f'{args}\nstdout={p.stdout}\nstderr={p.stderr}')
    if not ok and p.returncode==0: raise AssertionError(f'expected failure {args}')
    return p

class UserWorkflowTests(unittest.TestCase):
    def test_init_validate_evaluate_verify_compare(self):
        with tempfile.TemporaryDirectory() as tmp_text:
            tmp=Path(tmp_text); profiles=tmp/'profiles'; profiles.mkdir(); dataset=tmp/'dataset'
            scenes=[]
            for scene,ds in [('a','scene_a'),('b','scene_b')]:
                for folder in ('images','gt_masks','masks'): (dataset/ds/folder).mkdir(parents=True,exist_ok=True)
                ref=np.zeros((512,640,3),dtype=np.uint8); ref[...,0]=40 if scene=='a' else 80
                tool=np.zeros((512,640),dtype=np.uint8); tool[:10,:]=255
                invalid=np.zeros((512,640),dtype=np.uint8); invalid[-10:,:]=255
                Image.fromarray(ref).save(dataset/ds/'images'/'000001.png')
                Image.fromarray(tool).save(dataset/ds/'gt_masks'/'000001.png')
                Image.fromarray(invalid).save(dataset/ds/'masks'/'000001.png')
                frame={'frame_id':'000001','native_frame_id':1,'reference_sha256':sha(dataset/ds/'images'/'000001.png'),'tool_mask_sha256':sha(dataset/ds/'gt_masks'/'000001.png'),'invalid_mask_sha256':sha(dataset/ds/'masks'/'000001.png')}
                scenes.append({'scene':scene,'dataset_scene':ds,'reference_template':f'{ds}/images/{{frame_id}}.png','tool_mask_template':f'{ds}/gt_masks/{{frame_id}}.png','invalid_mask_template':f'{ds}/masks/{{frame_id}}.png','frames':[frame]})
            profile={'artifact':'endoeval_profile','schema_version':1,'profile_id':'test-rgb-v1','status':'ready','domain':'dynamic_endoscopic_reconstruction','task':'rgb_reconstruction','dataset':{'name':'Synthetic','release':'test-v1','authority':'test-rgb-v1-authority.json'},'submission':{'input':'rendered_rgb_images','path_template':'predictions/{scene}/{frame_id}.png','image_encoding':'png_rgb'},'measurement':{'output_target':'RGB reconstruction','support':'dataset-valid non-tool tissue','metric':{'family':'PSNR','convention':'psnr_mse_eps_1e-10','denominator':'true_exclusion','data_range':1.0},'frame_reduction':'unweighted_frame_mean','scene_reduction':'equal_scene_weight'},'outputs':['metrics.json','evaluation_receipt.json','paper_table.csv','admission.json']}
            authority={'artifact':'endoeval_dataset_authority','schema_version':1,'profile_id':'test-rgb-v1','dataset_release':'test-v1','dimensions_wh':[640,512],'support':{'definition':'not(tool_mask > 0.5) AND not(invalid_mask > 0.5)','threshold':0.5},'scenes':scenes,'source':{'test':True}}
            (profiles/'test-rgb-v1.json').write_text(json.dumps(profile)); (profiles/'test-rgb-v1-authority.json').write_text(json.dumps(authority))
            env=os.environ.copy(); env['ENDOEVAL_PROFILE_ROOT']=str(profiles); env['PYTHONPATH']=str(ROOT/'src')
            receipts=[]
            for method,offset in [('perfect',0),('shifted',5)]:
                sub=tmp/method
                run(['init',str(sub),'--profile','test-rgb-v1','--method',method],env)
                for scene,ds in [('a','scene_a'),('b','scene_b')]:
                    ref=np.asarray(Image.open(dataset/ds/'images'/'000001.png').convert('RGB'),dtype=np.uint8)
                    pred=np.clip(ref.astype(np.int16)+offset,0,255).astype(np.uint8)
                    Image.fromarray(pred).save(sub/'predictions'/scene/'000001.png')
                run(['validate',str(sub/'submission.json'),'--check-paths'],env)
                run(['evaluate',str(sub/'submission.json'),'--dataset-root',str(dataset)],env)
                receipt=sub/'endoeval-output'/'evaluation_receipt.json'; receipts.append(receipt)
                run(['verify',str(receipt)],env)
                self.assertEqual({p.name for p in (sub/'endoeval-output').iterdir()},{'metrics.json','evaluation_receipt.json','paper_table.csv','admission.json'})
            comp=json.loads(run(['compare',str(receipts[0]),str(receipts[1]),'--claim','ordering'],env).stdout)
            self.assertEqual(comp['disposition'],'identical'); self.assertEqual(comp['artifact_ordering'],'perfect > shifted')
            metrics=receipts[0].parent/'metrics.json'; metrics.write_text(metrics.read_text()+'\n')
            run(['verify',str(receipts[0])],env,ok=False)
if __name__=='__main__': unittest.main()
