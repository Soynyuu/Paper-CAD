// Part of the Chili3d Project, under the AGPL-3.0 License.
// See LICENSE file in the project root for full license information.

import { StepUnfoldService } from "chili-core";

/**
 * STEP Unfold機能のテストユーティリティ
 */
export class StepUnfoldTestUtils {
    static async testBackendConnection(): Promise<void> {
        console.log("Testing backend connection...");

        const service = new StepUnfoldService("http://localhost:8001/api");

        const result = await service.checkBackendHealth();

        if (result.isOk) {
            console.log("✅ Backend is healthy and ready");
        } else {
            console.error("❌ Backend health check failed:", result.error);
        }
    }

    static createSampleStepFile(): File {
        // 簡単なSTEPファイルの内容（BOXの例）
        const stepContent = `ISO-10303-21;
HEADER;
FILE_DESCRIPTION(('Open CASCADE Model'),'2;1');
FILE_NAME('box.step','2024-01-01T00:00:00',(''),(''),
'Open CASCADE 7.5.0','Open CASCADE 7.5.0','');
FILE_SCHEMA(('AUTOMOTIVE_DESIGN'));
ENDSEC;
DATA;
#1 = APPLICATION_PROTOCOL_DEFINITION('international standard',
'automotive_design',2000,#2);
#2 = APPLICATION_CONTEXT(
'core data for automotive mechanical design processes');
#3 = SHAPE_DEFINITION_REPRESENTATION(#4,#10);
#4 = PRODUCT_DEFINITION_SHAPE('','',#5);
#5 = PRODUCT_DEFINITION('design','',#6,#9);
#6 = PRODUCT_DEFINITION_FORMATION('','',#7);
#7 = PRODUCT('Box','Box','',(#8));
#8 = PRODUCT_CONTEXT('',#2,'mechanical');
#9 = PRODUCT_DEFINITION_CONTEXT('part definition',#2,'design');
#10 = ADVANCED_BREP_SHAPE_REPRESENTATION('',(#11,#15),#43);
#11 = MANIFOLD_SOLID_BREP('',#12);
#12 = CLOSED_SHELL('',(#13));
#13 = ADVANCED_FACE('',(#14),#40,.T.);
#14 = FACE_OUTER_BOUND('',#19,.T.);
#15 = AXIS2_PLACEMENT_3D('',#16,#17,#18);
#16 = CARTESIAN_POINT('',(0.,0.,0.));
#17 = DIRECTION('',(0.,0.,1.));
#18 = DIRECTION('',(1.,0.,0.));
#19 = EDGE_LOOP('',(#20,#25,#30,#35));
#20 = ORIENTED_EDGE('',*,*,#21,.F.);
#21 = EDGE_CURVE('',#22,#23,#24,.T.);
#22 = VERTEX_POINT('',#44);
#23 = VERTEX_POINT('',#45);
#24 = LINE('',#46,#47);
#25 = ORIENTED_EDGE('',*,*,#26,.F.);
#26 = EDGE_CURVE('',#27,#22,#28,.T.);
#27 = VERTEX_POINT('',#48);
#28 = LINE('',#49,#50);
#29 = ORIENTED_EDGE('',*,*,#30,.F.);
#30 = EDGE_CURVE('',#31,#27,#32,.T.);
#31 = VERTEX_POINT('',#51);
#32 = LINE('',#52,#53);
#33 = ORIENTED_EDGE('',*,*,#34,.F.);
#34 = EDGE_CURVE('',#23,#31,#35,.T.);
#35 = LINE('',#54,#55);
#36 = PLANE('',#56);
#37 = ADVANCED_FACE('',(#38),#36,.T.);
#38 = FACE_OUTER_BOUND('',#39,.T.);
#39 = EDGE_LOOP('',(#20,#25,#29,#33));
#40 = PLANE('',#57);
#41 = ADVANCED_FACE('',(#42),#40,.T.);
#42 = FACE_OUTER_BOUND('',#14,.T.);
#43 = ( GEOMETRIC_REPRESENTATION_CONTEXT(3) 
GLOBAL_UNCERTAINTY_ASSIGNED_CONTEXT((#58)) GLOBAL_UNIT_ASSIGNED_CONTEXT
((#59,#60,#61)) REPRESENTATION_CONTEXT('Context #1',
'3D Context with UNIT and UNCERTAINTY') );
#44 = CARTESIAN_POINT('',(0.,0.,0.));
#45 = CARTESIAN_POINT('',(10.,0.,0.));
#46 = CARTESIAN_POINT('',(0.,0.,0.));
#47 = VECTOR('',#62,10.);
#48 = CARTESIAN_POINT('',(0.,10.,0.));
#49 = CARTESIAN_POINT('',(0.,10.,0.));
#50 = VECTOR('',#63,10.);
#51 = CARTESIAN_POINT('',(10.,10.,0.));
#52 = CARTESIAN_POINT('',(10.,10.,0.));
#53 = VECTOR('',#64,10.);
#54 = CARTESIAN_POINT('',(10.,0.,0.));
#55 = VECTOR('',#65,10.);
#56 = AXIS2_PLACEMENT_3D('',#66,#67,#68);
#57 = AXIS2_PLACEMENT_3D('',#69,#70,#71);
#58 = UNCERTAINTY_MEASURE_WITH_UNIT(LENGTH_MEASURE(1.E-07),#59,
'distance_accuracy_value','confusion accuracy');
#59 = ( LENGTH_UNIT() NAMED_UNIT(*) SI_UNIT(.MILLI.,.METRE.) );
#60 = ( NAMED_UNIT(*) PLANE_ANGLE_UNIT() SI_UNIT($,.RADIAN.) );
#61 = ( NAMED_UNIT(*) SI_UNIT($,.STERADIAN.) SOLID_ANGLE_UNIT() );
#62 = DIRECTION('',(1.,0.,0.));
#63 = DIRECTION('',(0.,-1.,0.));
#64 = DIRECTION('',(-1.,0.,0.));
#65 = DIRECTION('',(0.,1.,0.));
#66 = CARTESIAN_POINT('',(0.,0.,0.));
#67 = DIRECTION('',(0.,0.,1.));
#68 = DIRECTION('',(1.,0.,0.));
#69 = CARTESIAN_POINT('',(0.,0.,0.));
#70 = DIRECTION('',(0.,0.,1.));
#71 = DIRECTION('',(1.,0.,0.));
ENDSEC;
END-ISO-10303-21;
`;

        return new File([stepContent], "test-box.step", { type: "application/step" });
    }
}

// デバッグ用: グローバルに公開
declare global {
    interface Window {
        stepUnfoldTestUtils: typeof StepUnfoldTestUtils;
    }
}

if (typeof window !== "undefined") {
    window.stepUnfoldTestUtils = StepUnfoldTestUtils;
}
