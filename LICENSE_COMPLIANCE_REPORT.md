# License Compliance Investigation Report

**Date**: 2026-01-30  
**Repository**: Soynyuu/Paper-CAD  
**Status**: ✅ RESOLVED

## Executive Summary

This investigation identified and resolved critical license compliance issues in the Paper-CAD repository. The main issue was that the README claimed the project was under "MIT License," but the actual codebase is based on the AGPL-3.0 licensed chili3d project and contained an AGPL-3.0 license file without proper attribution.

## Critical Issues Found

### 1. ❌ License Mismatch (RESOLVED)
- **Issue**: README.md claimed "MIT License" 
- **Reality**: Code is derivative of chili3d (AGPL-3.0)
- **Risk**: Severe legal liability, license violation
- **Resolution**: ✅ Updated README to correctly state AGPL-3.0

### 2. ❌ Missing Root LICENSE File (RESOLVED)
- **Issue**: No LICENSE file in repository root
- **Risk**: License terms unclear to users/contributors
- **Resolution**: ✅ Added AGPL-3.0 LICENSE file to root

### 3. ❌ Missing Attribution (RESOLVED)
- **Issue**: No acknowledgment of upstream chili3d project
- **Risk**: Copyright violation, failure to comply with AGPL terms
- **Resolution**: ✅ Added attribution in README and created NOTICE file

### 4. ❌ Missing License Metadata (RESOLVED)
- **Issue**: No "license" field in package.json files
- **Risk**: NPM ecosystem misrepresentation
- **Resolution**: ✅ Added "license": "AGPL-3.0" to all package.json files

## Upstream Project Information

**Project**: chili3d  
**Repository**: https://github.com/xiangechen/chili3d  
**Author**: 仙阁 (xiangetg@msn.cn)  
**Stars**: 4,099+  
**License**: GNU Affero General Public License v3.0 (AGPL-3.0)  
**Description**: Browser-based 3D CAD application built with TypeScript, OpenCASCADE, and Three.js

## Evidence of Derivative Work

1. **Package Naming**: All frontend packages use "chili-*" naming convention matching upstream
2. **cpp/README.md**: Explicitly states "chili3d's WebAssembly Module"
3. **Storage Keys**: Code references "chili3d" in storage keys
4. **Architecture**: Identical monorepo structure with same package organization
5. **LICENSE File**: Contains identical AGPL-3.0 text as upstream

## Changes Made

### Files Added
- ✅ `LICENSE` - AGPL-3.0 license text in repository root
- ✅ `NOTICE` - Detailed attribution and copyright notices

### Files Modified
- ✅ `README.md` - Updated license section and added chili3d attribution
- ✅ `frontend/package.json` - Added license field and metadata
- ✅ `frontend/packages/*/package.json` (13 files) - Added license field
- ✅ `lp/package.json` - Added license field

## Key Dependencies and Their Licenses

### Compatible with AGPL-3.0

✅ **OpenCASCADE Technology** - LGPL v2.1 with exception (compatible)  
✅ **Three.js** - MIT License (compatible)  
✅ **FastAPI** - MIT License (compatible)  
✅ **pythonOCC** - LGPL v3.0 (compatible)  
✅ **React** - MIT License (compatible)  
✅ **Cesium** - Apache 2.0 (compatible)

All major dependencies are compatible with AGPL-3.0.

## AGPL-3.0 Implications

### What This License Means

1. **Source Code Availability**: Any deployment of this software (including web services) must provide source code to users
2. **Derivative Works**: Must also be licensed under AGPL-3.0
3. **Network Use**: Network use counts as distribution (unlike GPL)
4. **Commercial Use**: Allowed, but must still provide source code

### Commercial Licensing

For commercial use without AGPL obligations, contact the upstream author:
- **Email**: xiangetg@msn.cn
- **Project**: chili3d

## Compliance Status

| Requirement | Before | After |
|-------------|--------|-------|
| Correct license stated | ❌ (claimed MIT) | ✅ (AGPL-3.0) |
| LICENSE file in root | ❌ Missing | ✅ Present |
| Attribution to upstream | ❌ Missing | ✅ Added |
| License in package.json | ❌ Missing | ✅ Added |
| NOTICE file | ❌ Missing | ✅ Created |

## Recommendations

### Completed ✅
1. Add LICENSE file to repository root
2. Correct license statement in README
3. Add attribution to chili3d
4. Add license fields to package.json
5. Create NOTICE file with detailed attribution

### Optional Future Improvements
1. Add copyright headers to source files (optional but good practice)
2. Add AGPL notice to web UI footer (recommended for transparency)
3. Document modifications made to upstream code
4. Consider contributing improvements back to upstream chili3d

### If Commercial License Needed
If you need to use this software commercially without AGPL obligations:
1. Contact upstream author: xiangetg@msn.cn
2. Negotiate commercial license for chili3d
3. Update LICENSE and NOTICE files accordingly

## Conclusion

All critical license compliance issues have been resolved. The repository now:
- ✅ Has correct license (AGPL-3.0)
- ✅ Provides proper attribution to upstream project
- ✅ Includes all required legal notices
- ✅ Has clear licensing metadata

The repository is now compliant with AGPL-3.0 requirements and properly acknowledges its derivative nature from the chili3d project.

---

**Investigator**: GitHub Copilot  
**Date**: 2026-01-30
