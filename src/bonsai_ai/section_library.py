from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import math
import re
from typing import Any, Dict, Iterable, List

from .contracts import MaterialSpec, SectionSpec

INCH_TO_M = 0.0254
IN2_TO_M2 = INCH_TO_M**2
IN3_TO_M3 = INCH_TO_M**3
IN4_TO_M4 = INCH_TO_M**4
LB_PER_FT_TO_N_PER_M = 14.593902937206362
KSI_TO_PA = 6_894_757.293168

AISC_V16_SOURCE_URL = "https://www.aisc.org/aisc/publications/steel-construction-manual/aisc-shapes-database-v160/"


@dataclass(frozen=True)
class CatalogSectionRecord:
    name: str
    shape_family: str
    material_id: str
    area_in2: float
    ix_in4: float
    iy_in4: float
    j_in4: float
    weight_lb_per_ft: float
    depth_in: float
    width_in: float
    tw_in: float | None = None
    tf_in: float | None = None
    thickness_in: float | None = None
    source: str = AISC_V16_SOURCE_URL

    @property
    def area_m2(self) -> float:
        return self.area_in2 * IN2_TO_M2

    @property
    def ix_m4(self) -> float:
        return self.ix_in4 * IN4_TO_M4

    @property
    def iy_m4(self) -> float:
        return self.iy_in4 * IN4_TO_M4

    @property
    def j_m4(self) -> float:
        return self.j_in4 * IN4_TO_M4

    @property
    def depth_m(self) -> float:
        return self.depth_in * INCH_TO_M

    @property
    def width_m(self) -> float:
        return self.width_in * INCH_TO_M

    @property
    def weight_n_per_m(self) -> float:
        return self.weight_lb_per_ft * LB_PER_FT_TO_N_PER_M

    @property
    def section_modulus_major_m3(self) -> float:
        half_depth = max(self.depth_m / 2.0, 1e-9)
        return self.ix_m4 / half_depth

    @property
    def section_modulus_minor_m3(self) -> float:
        half_width = max(self.width_m / 2.0, 1e-9)
        return self.iy_m4 / half_width


def starter_catalog_material_specs() -> List[MaterialSpec]:
    return [
        MaterialSpec(
            id="steel_w_shapes",
            family="steel",
            model="elastic_isotropic",
            properties={
                "density_kg_m3": 7850,
                "elastic_modulus_pa": 200_000_000_000,
                "poisson_ratio": 0.3,
                "fy_pa": 50.0 * KSI_TO_PA,
                "fu_pa": 65.0 * KSI_TO_PA,
                "source": AISC_V16_SOURCE_URL,
            },
        ),
        MaterialSpec(
            id="steel_hss",
            family="steel",
            model="elastic_isotropic",
            properties={
                "density_kg_m3": 7850,
                "elastic_modulus_pa": 200_000_000_000,
                "poisson_ratio": 0.3,
                "fy_pa": 50.0 * KSI_TO_PA,
                "fu_pa": 62.0 * KSI_TO_PA,
                "source": AISC_V16_SOURCE_URL,
            },
        ),
        MaterialSpec(
            id="steel_rod",
            family="steel",
            model="elastic_isotropic",
            properties={
                "density_kg_m3": 7850,
                "elastic_modulus_pa": 200_000_000_000,
                "poisson_ratio": 0.3,
                "fy_pa": 36.0 * KSI_TO_PA,
                "fu_pa": 58.0 * KSI_TO_PA,
                "source": "derived_starter_defaults",
            },
        ),
    ]


def starter_section_records() -> Dict[str, CatalogSectionRecord]:
    records = {
        "W10X33": _w_record("W10X33", 33, 9.71, 171, 36.6, 0.583, 9.73, 7.96, 0.29, 0.435),
        "W10X49": _w_record("W10X49", 49, 14.4, 272, 93.4, 1.39, 10.0, 10.0, 0.34, 0.56),
        "W12X40": _w_record("W12X40", 40, 11.7, 307, 44.1, 0.906, 11.9, 8.01, 0.295, 0.515),
        "W12X53": _w_record("W12X53", 53, 15.6, 425, 95.8, 1.58, 12.1, 10.0, 0.345, 0.575),
        "W14X68": _w_record("W14X68", 68, 20.0, 722, 121, 3.01, 14.0, 10.0, 0.415, 0.72),
        "W14X90": _w_record("W14X90", 90, 26.5, 999, 362, 4.06, 14.0, 14.5, 0.44, 0.71),
        "W16X77": _w_record("W16X77", 77, 22.6, 1110, 138, 3.57, 16.5, 10.3, 0.455, 0.76),
        "W18X86": _w_record("W18X86", 86, 25.3, 1530, 175, 4.1, 18.4, 11.1, 0.48, 0.77),
        "W12X26": _w_record("W12X26", 26, 7.65, 204, 17.3, 0.3, 12.2, 6.49, 0.23, 0.38),
        "W12X35": _w_record("W12X35", 35, 10.3, 285, 24.5, 0.741, 12.5, 6.56, 0.3, 0.52),
        "W14X30": _w_record("W14X30", 30, 8.85, 291, 19.6, 0.38, 13.8, 6.73, 0.27, 0.385),
        "W16X31": _w_record("W16X31", 31, 9.13, 375, 12.4, 0.461, 15.9, 5.53, 0.275, 0.44),
        "W18X35": _w_record("W18X35", 35, 10.3, 510, 15.3, 0.506, 17.7, 6.0, 0.3, 0.425),
        "W21X44": _w_record("W21X44", 44, 13.0, 843, 20.7, 0.77, 20.7, 6.5, 0.35, 0.45),
        "W24X55": _w_record("W24X55", 55, 16.2, 1350, 29.1, 1.18, 23.6, 7.01, 0.395, 0.505),
        "W27X84": _w_record("W27X84", 84, 24.7, 2850, 106, 2.81, 26.7, 10.0, 0.46, 0.64),
        "W8X18": _w_record("W8X18", 18, 5.26, 61.9, 7.97, 0.172, 8.14, 5.25, 0.23, 0.33),
        "W10X22": _w_record("W10X22", 22, 6.49, 118, 11.4, 0.239, 10.2, 5.75, 0.24, 0.36),
        "HSS6X6X3/8": _hss_record("HSS6X6X3/8", 27.48, 7.58, 39.5, 39.5, 64.6, 6.0, 6.0, 0.375),
        "HSS8X8X3/8": _hss_record("HSS8X8X3/8", 37.69, 10.4, 100, 100, 160, 8.0, 8.0, 0.375),
        "HSS10X10X1/2": _hss_record("HSS10X10X1/2", 62.46, 17.2, 256, 256, 412, 10.0, 10.0, 0.5),
        "HSS12X12X1/2": _hss_record("HSS12X12X1/2", 76.07, 20.9, 457, 457, 728, 12.0, 12.0, 0.5),
        "HSS4X4X1/4": _hss_record("HSS4X4X1/4", 12.21, 3.37, 7.8, 7.8, 12.8, 4.0, 4.0, 0.25),
        "HSS6X6X1/4": _hss_record("HSS6X6X1/4", 19.02, 5.24, 28.6, 28.6, 45.6, 6.0, 6.0, 0.25),
        'ROD1"': _rod_record('ROD1"', 1.0),
        'ROD1-1/4"': _rod_record('ROD1-1/4"', 1.25),
        'ROD1-1/2"': _rod_record('ROD1-1/2"', 1.5),
    }
    return records


def resolve_catalog_section(family_id: str, section_name: str, material_id: str | None = None) -> SectionSpec | None:
    record = starter_section_records().get(section_name.upper())
    if record is None:
        return None
    resolved_material_id = material_id or record.material_id
    dimensions = {
        "width": record.width_m,
        "depth": record.depth_m,
    }
    if record.tw_in is not None:
        dimensions["web_thickness"] = record.tw_in * INCH_TO_M
    if record.tf_in is not None:
        dimensions["flange_thickness"] = record.tf_in * INCH_TO_M
    if record.thickness_in is not None:
        dimensions["thickness"] = record.thickness_in * INCH_TO_M
    metadata = {
        "catalog_family_id": family_id,
        "catalog_section_name": record.name,
        "shape_family": record.shape_family,
        "section_properties": {
            "area_m2": record.area_m2,
            "ix_m4": record.ix_m4,
            "iy_m4": record.iy_m4,
            "j_m4": record.j_m4,
            "section_modulus_major_m3": record.section_modulus_major_m3,
            "section_modulus_minor_m3": record.section_modulus_minor_m3,
            "weight_n_per_m": record.weight_n_per_m,
            "weight_lb_per_ft": record.weight_lb_per_ft,
        },
        "source": record.source,
        "imperial_reference": {
            "area_in2": record.area_in2,
            "ix_in4": record.ix_in4,
            "iy_in4": record.iy_in4,
            "j_in4": record.j_in4,
            "depth_in": record.depth_in,
            "width_in": record.width_in,
            "tw_in": record.tw_in,
            "tf_in": record.tf_in,
            "thickness_in": record.thickness_in,
        },
    }
    return SectionSpec(
        id=_section_spec_id(family_id, record.name),
        kind="catalog_profile",
        material_id=resolved_material_id,
        dimensions=dimensions,
        metadata=metadata,
    )


def catalog_material_ids() -> Iterable[str]:
    return [material.id for material in starter_catalog_material_specs()]


def family_material_id(catalog: Dict[str, Any], family_id: str) -> str | None:
    for family in list(catalog.get("member_families", [])) + list(catalog.get("footing_families", [])):
        if family.get("id") == family_id:
            material_id = str(family.get("material") or "").strip()
            if material_id:
                return material_id
    return None


def _section_spec_id(family_id: str, section_name: str) -> str:
    safe = re.sub(r"[^a-z0-9]+", "_", section_name.lower()).strip("_")
    return f"catalog_{family_id}_{safe}"


def _w_record(
    name: str,
    weight_lb_per_ft: float,
    area_in2: float,
    ix_in4: float,
    iy_in4: float,
    j_in4: float,
    depth_in: float,
    width_in: float,
    tw_in: float,
    tf_in: float,
) -> CatalogSectionRecord:
    return CatalogSectionRecord(
        name=name.upper(),
        shape_family="W",
        material_id="steel_w_shapes",
        area_in2=area_in2,
        ix_in4=ix_in4,
        iy_in4=iy_in4,
        j_in4=j_in4,
        weight_lb_per_ft=weight_lb_per_ft,
        depth_in=depth_in,
        width_in=width_in,
        tw_in=tw_in,
        tf_in=tf_in,
    )


def _hss_record(
    name: str,
    weight_lb_per_ft: float,
    area_in2: float,
    ix_in4: float,
    iy_in4: float,
    j_in4: float,
    depth_in: float,
    width_in: float,
    thickness_in: float,
) -> CatalogSectionRecord:
    return CatalogSectionRecord(
        name=name.upper(),
        shape_family="HSS",
        material_id="steel_hss",
        area_in2=area_in2,
        ix_in4=ix_in4,
        iy_in4=iy_in4,
        j_in4=j_in4,
        weight_lb_per_ft=weight_lb_per_ft,
        depth_in=depth_in,
        width_in=width_in,
        thickness_in=thickness_in,
    )


def _rod_record(name: str, diameter_in: float) -> CatalogSectionRecord:
    radius = diameter_in / 2.0
    area_in2 = math.pi * radius * radius
    j_in4 = math.pi * diameter_in**4 / 32.0
    ix_in4 = math.pi * diameter_in**4 / 64.0
    weight_lb_per_ft = area_in2 * 12.0 * 0.283
    return CatalogSectionRecord(
        name=name.upper(),
        shape_family="ROD",
        material_id="steel_rod",
        area_in2=area_in2,
        ix_in4=ix_in4,
        iy_in4=ix_in4,
        j_in4=j_in4,
        weight_lb_per_ft=weight_lb_per_ft,
        depth_in=diameter_in,
        width_in=diameter_in,
        thickness_in=diameter_in,
        source="derived_starter_defaults",
    )
