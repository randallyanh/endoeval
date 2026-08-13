from __future__ import annotations
import math,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'src'))
from benchmark_integrity.comparability import ComparisonFacts,assess_comparability
from benchmark_integrity.metric_conventions import FINITE_PSNR_CONVENTION,psnr_from_mse
from benchmark_integrity.region_error import RegionErrorStats,compare_psnr_denominators

class KernelConformanceTests(unittest.TestCase):
    def test_load_bearing_boundary(self):
        self.assertTrue(math.isclose(psnr_from_mse(0.01,convention=FINITE_PSNR_CONVENTION),19.99999995657055,rel_tol=0,abs_tol=1e-12))
        result=compare_psnr_denominators(RegionErrorStats(4,2,0.06,0.12),convention=FINITE_PSNR_CONVENTION)
        self.assertEqual(result.status,'complete')
        base=dict(source_identity='0'*64,target_identity='1'*64,output_target_equal=True,source_measurement_determined=True,target_measurement_determined=True,frame_population_equal=True,mask_support_equal=True,scoring_protocol_equal=True,metric_definition_equal=True,reduction_equal=True)
        self.assertEqual(assess_comparability(claim_mode='ordering',facts=ComparisonFacts(**base)).disposition,'identical')
        base['mask_support_equal']=False
        self.assertEqual(assess_comparability(claim_mode='ordering',facts=ComparisonFacts(**base)).disposition,'rescore_required')
        self.assertEqual(assess_comparability(claim_mode='capability',facts=ComparisonFacts(**base)).disposition,'rerun_required')
if __name__=='__main__': unittest.main()
