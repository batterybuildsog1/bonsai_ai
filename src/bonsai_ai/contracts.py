from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class AnalysisDomain(str, Enum):
    WIND = "wind"
    SEISMIC = "seismic"
    GRAVITY = "gravity"
    FOOTING = "footing"
    STRUCTURAL_STEEL = "structural_steel"


class AnalysisProfile(str, Enum):
    GLOBAL_FAST = "global_fast"
    GLOBAL_FULL = "global_full"
    FACADE_SUPPORT = "facade_support"
    SUBSTRUCTURE = "substructure"


class EngineeringModelScope(str, Enum):
    GLOBAL_FRAME = "global_frame"
    ROOF_LOAD_PATH = "roof_load_path"
    FACADE_SUPPORT = "facade_support"
    SUBSTRUCTURE = "substructure"
    OPENING_SUPPORT = "opening_support"


class ArtifactKind(str, Enum):
    DESIGN_BRIEF = "design_brief"
    DESIGN_PACKAGE = "design_package"
    BIM_PLAN = "bim_plan"
    PHYSICAL_IFC = "physical_ifc"
    STRUCTURAL_SOURCE_MODEL = "structural_source_model"
    ANALYTICAL_MODEL = "analytical_model"
    ENGINEERING_MODEL = "engineering_model"
    SOLVER_INPUT = "solver_input"
    SOLVER_RESULT = "solver_result"
    RESULTS_BUNDLE = "results_bundle"
    REVIEW_RENDER = "review_render"
    ENGINEERING_REPORT = "engineering_report"


class ArtifactFormat(str, Enum):
    JSON = "json"
    PY = "py"
    FCSTD = "fcstd"
    IFC = "ifc"
    IFCZIP = "ifczip"
    PDF = "pdf"
    PNG = "png"
    GLB = "glb"
    CALCULIX_INP = "calculix_inp"
    CODE_ASTER = "code_aster"
    PYNITE_JSON = "pynite_json"
    UNKNOWN = "unknown"


class ArtifactRole(str, Enum):
    MANIFEST = "manifest"
    BIM_PLAN = "bim_plan"
    PRIMARY_IFC = "primary_ifc"
    STRUCTURAL_SOURCE_MODEL = "structural_source_model"
    ANALYSIS_MODEL = "analysis_model"
    ENGINEERING_MODEL = "engineering_model"
    FREECAD_MODEL = "freecad_model"
    SOLVER_INPUT = "solver_input"
    SOLVER_RESULT = "solver_result"
    FREECAD_HANDOFF = "freecad_handoff"
    RESULTS_BUNDLE = "results_bundle"
    REVIEW_RENDER = "review_render"
    ENGINEERING_REPORT = "engineering_report"


@dataclass
class SourceDocument:
    name: str
    path: str
    role: str = "reference"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LoadAction:
    target_id: str
    kind: str
    direction: Optional[str] = None
    magnitude: Any = None
    distribution: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LoadCase:
    name: str
    domain: AnalysisDomain
    code_basis: str
    category: str = "strength"
    design_situation: str = "persistent"
    parameters: Dict[str, Any] = field(default_factory=dict)
    actions: List[LoadAction] = field(default_factory=list)


@dataclass
class LoadCombination:
    name: str
    case_factors: Dict[str, float]
    category: str = "strength"
    code_basis: str = "unspecified"


@dataclass
class MaterialSpec:
    id: str
    family: str
    model: str
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SectionSpec:
    id: str
    kind: str
    material_id: str
    dimensions: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SupportSpec:
    id: str
    target_id: str
    target_kind: str
    restraints: Dict[str, bool] = field(default_factory=dict)
    spring_stiffness: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StructuralElement:
    id: str
    kind: str
    geometry: Dict[str, Any] = field(default_factory=dict)
    section_id: Optional[str] = None
    storey: Optional[str] = None
    orientation: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StructuralSourceElement:
    id: str
    kind: str
    role: str
    structural_family: str = "generic"
    parent_id: Optional[str] = None
    system_id: Optional[str] = None
    assembly_id: Optional[str] = None
    layout_zone_id: Optional[str] = None
    layout_zone_kind: Optional[str] = None
    interface_type: Optional[str] = None
    geometry: Dict[str, Any] = field(default_factory=dict)
    section_id: Optional[str] = None
    storey: Optional[str] = None
    orientation: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StructuralSourceModel:
    units: str = "meters"
    materials: List[MaterialSpec] = field(default_factory=list)
    sections: List[SectionSpec] = field(default_factory=list)
    elements: List[StructuralSourceElement] = field(default_factory=list)
    supports: List[SupportSpec] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AnalyticalModel:
    units: str = "meters"
    materials: List[MaterialSpec] = field(default_factory=list)
    sections: List[SectionSpec] = field(default_factory=list)
    elements: List[StructuralElement] = field(default_factory=list)
    supports: List[SupportSpec] = field(default_factory=list)
    load_cases: List[LoadCase] = field(default_factory=list)
    load_combinations: List[LoadCombination] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EngineeringModel:
    units: str = "meters"
    scope: str = "unspecified"
    materials: List[MaterialSpec] = field(default_factory=list)
    sections: List[SectionSpec] = field(default_factory=list)
    elements: List[StructuralElement] = field(default_factory=list)
    supports: List[SupportSpec] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DesignBrief:
    prompt: str
    documents: List[SourceDocument] = field(default_factory=list)
    scene_context: Optional[Dict[str, Any]] = None
    constraints: List[str] = field(default_factory=list)
    analysis_domains: List[AnalysisDomain] = field(default_factory=list)
    load_cases: List[LoadCase] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PhysicalModelSpec:
    summary: str
    assumptions: List[str]
    plan: Dict[str, Any]
    authored_plan: Optional[Dict[str, Any]] = None
    semantic_model: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineArtifact:
    kind: ArtifactKind
    format: ArtifactFormat
    path: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AnalysisRequest:
    solver: str
    design_codes: List[str]
    load_cases: List[LoadCase]
    load_combinations: List[LoadCombination] = field(default_factory=list)
    export_options: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AnalysisResult:
    solver: str
    status: str = "completed"
    governing_cases: List[str] = field(default_factory=list)
    unity_checks: Dict[str, float] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    artifacts: List[PipelineArtifact] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NormalizedArtifactRef:
    kind: ArtifactKind
    format: ArtifactFormat
    path: str
    role: ArtifactRole
    label: str
    is_primary: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PhysicalSummary:
    summary: str = ""
    assumptions: List[str] = field(default_factory=list)
    created: List[str] = field(default_factory=list)
    element_counts: Dict[str, int] = field(default_factory=dict)
    storeys: List[str] = field(default_factory=list)
    planner_metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AnalysisSummary:
    status: str = "not_requested"
    domains: List[str] = field(default_factory=list)
    load_cases: List[str] = field(default_factory=list)
    load_combinations: List[str] = field(default_factory=list)
    solver: Optional[str] = None
    design_codes: List[str] = field(default_factory=list)
    governing_cases: List[str] = field(default_factory=list)
    unity_checks: Dict[str, float] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)


@dataclass
class ResultsBundle:
    schema_version: str
    entrypoints: Dict[str, Optional[str]] = field(default_factory=dict)
    artifacts: List[NormalizedArtifactRef] = field(default_factory=list)
    physical_summary: PhysicalSummary = field(default_factory=PhysicalSummary)
    analysis_summary: AnalysisSummary = field(default_factory=AnalysisSummary)
    diagnostics: Dict[str, Any] = field(default_factory=dict)
    blender_payload: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DesignPackage:
    brief: DesignBrief
    physical_model: Optional[PhysicalModelSpec] = None
    structural_source_model: Optional[StructuralSourceModel] = None
    system_layout: Dict[str, Any] = field(default_factory=dict)
    load_path_model: Dict[str, Any] = field(default_factory=dict)
    catalog_selection_summary: Dict[str, Any] = field(default_factory=dict)
    analytical_model: Optional[AnalyticalModel] = None
    engineering_models: Dict[str, EngineeringModel] = field(default_factory=dict)
    engineering_model_summary: Dict[str, Any] = field(default_factory=dict)
    physical_artifacts: List[PipelineArtifact] = field(default_factory=list)
    analysis_request: Optional[AnalysisRequest] = None
    analysis_artifacts: List[PipelineArtifact] = field(default_factory=list)
    analysis_result: Optional[AnalysisResult] = None
    results_artifacts: List[PipelineArtifact] = field(default_factory=list)
    review_artifacts: List[PipelineArtifact] = field(default_factory=list)

    def to_manifest(self) -> Dict[str, Any]:
        return asdict(self)
