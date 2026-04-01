// viewer/node_modules/@ifc-lite/data/dist/string-table.js
var StringTable = class {
  strings = [""];
  index = /* @__PURE__ */ new Map([["", 0]]);
  NULL_INDEX = -1;
  get count() {
    return this.strings.length;
  }
  /**
   * Get string by index
   */
  get(idx) {
    if (idx < 0 || idx >= this.strings.length) {
      return "";
    }
    return this.strings[idx];
  }
  /**
   * Intern string (add if not exists, return index)
   */
  intern(value) {
    if (value === null || value === void 0) {
      return this.NULL_INDEX;
    }
    const existing = this.index.get(value);
    if (existing !== void 0) {
      return existing;
    }
    const newIndex = this.strings.length;
    this.strings.push(value);
    this.index.set(value, newIndex);
    return newIndex;
  }
  /**
   * Check if string exists
   */
  has(value) {
    return this.index.has(value);
  }
  /**
   * Get index of string (returns -1 if not found)
   */
  indexOf(value) {
    return this.index.get(value) ?? -1;
  }
  /**
   * Get all strings (for debugging/export)
   */
  getAll() {
    return [...this.strings];
  }
};

// viewer/node_modules/@ifc-lite/data/dist/types.js
var IfcTypeEnum;
(function(IfcTypeEnum2) {
  IfcTypeEnum2[IfcTypeEnum2["IfcProject"] = 1] = "IfcProject";
  IfcTypeEnum2[IfcTypeEnum2["IfcSite"] = 2] = "IfcSite";
  IfcTypeEnum2[IfcTypeEnum2["IfcBuilding"] = 3] = "IfcBuilding";
  IfcTypeEnum2[IfcTypeEnum2["IfcBuildingStorey"] = 4] = "IfcBuildingStorey";
  IfcTypeEnum2[IfcTypeEnum2["IfcSpace"] = 5] = "IfcSpace";
  IfcTypeEnum2[IfcTypeEnum2["IfcFacility"] = 59] = "IfcFacility";
  IfcTypeEnum2[IfcTypeEnum2["IfcFacilityPart"] = 60] = "IfcFacilityPart";
  IfcTypeEnum2[IfcTypeEnum2["IfcBridge"] = 61] = "IfcBridge";
  IfcTypeEnum2[IfcTypeEnum2["IfcBridgePart"] = 62] = "IfcBridgePart";
  IfcTypeEnum2[IfcTypeEnum2["IfcRoad"] = 63] = "IfcRoad";
  IfcTypeEnum2[IfcTypeEnum2["IfcRoadPart"] = 64] = "IfcRoadPart";
  IfcTypeEnum2[IfcTypeEnum2["IfcRailway"] = 65] = "IfcRailway";
  IfcTypeEnum2[IfcTypeEnum2["IfcRailwayPart"] = 66] = "IfcRailwayPart";
  IfcTypeEnum2[IfcTypeEnum2["IfcMarineFacility"] = 67] = "IfcMarineFacility";
  IfcTypeEnum2[IfcTypeEnum2["IfcWall"] = 10] = "IfcWall";
  IfcTypeEnum2[IfcTypeEnum2["IfcWallStandardCase"] = 11] = "IfcWallStandardCase";
  IfcTypeEnum2[IfcTypeEnum2["IfcDoor"] = 12] = "IfcDoor";
  IfcTypeEnum2[IfcTypeEnum2["IfcWindow"] = 13] = "IfcWindow";
  IfcTypeEnum2[IfcTypeEnum2["IfcSlab"] = 14] = "IfcSlab";
  IfcTypeEnum2[IfcTypeEnum2["IfcColumn"] = 15] = "IfcColumn";
  IfcTypeEnum2[IfcTypeEnum2["IfcBeam"] = 16] = "IfcBeam";
  IfcTypeEnum2[IfcTypeEnum2["IfcStair"] = 17] = "IfcStair";
  IfcTypeEnum2[IfcTypeEnum2["IfcRamp"] = 18] = "IfcRamp";
  IfcTypeEnum2[IfcTypeEnum2["IfcRoof"] = 19] = "IfcRoof";
  IfcTypeEnum2[IfcTypeEnum2["IfcCovering"] = 20] = "IfcCovering";
  IfcTypeEnum2[IfcTypeEnum2["IfcCurtainWall"] = 21] = "IfcCurtainWall";
  IfcTypeEnum2[IfcTypeEnum2["IfcRailing"] = 22] = "IfcRailing";
  IfcTypeEnum2[IfcTypeEnum2["IfcPile"] = 23] = "IfcPile";
  IfcTypeEnum2[IfcTypeEnum2["IfcMember"] = 24] = "IfcMember";
  IfcTypeEnum2[IfcTypeEnum2["IfcPlate"] = 25] = "IfcPlate";
  IfcTypeEnum2[IfcTypeEnum2["IfcFooting"] = 26] = "IfcFooting";
  IfcTypeEnum2[IfcTypeEnum2["IfcBuildingElementProxy"] = 27] = "IfcBuildingElementProxy";
  IfcTypeEnum2[IfcTypeEnum2["IfcStairFlight"] = 28] = "IfcStairFlight";
  IfcTypeEnum2[IfcTypeEnum2["IfcRampFlight"] = 29] = "IfcRampFlight";
  IfcTypeEnum2[IfcTypeEnum2["IfcChimney"] = 31] = "IfcChimney";
  IfcTypeEnum2[IfcTypeEnum2["IfcShadingDevice"] = 32] = "IfcShadingDevice";
  IfcTypeEnum2[IfcTypeEnum2["IfcBuildingElementPart"] = 33] = "IfcBuildingElementPart";
  IfcTypeEnum2[IfcTypeEnum2["IfcOpeningElement"] = 30] = "IfcOpeningElement";
  IfcTypeEnum2[IfcTypeEnum2["IfcElementAssembly"] = 34] = "IfcElementAssembly";
  IfcTypeEnum2[IfcTypeEnum2["IfcReinforcingBar"] = 35] = "IfcReinforcingBar";
  IfcTypeEnum2[IfcTypeEnum2["IfcReinforcingMesh"] = 36] = "IfcReinforcingMesh";
  IfcTypeEnum2[IfcTypeEnum2["IfcTendon"] = 37] = "IfcTendon";
  IfcTypeEnum2[IfcTypeEnum2["IfcDiscreteAccessory"] = 38] = "IfcDiscreteAccessory";
  IfcTypeEnum2[IfcTypeEnum2["IfcMechanicalFastener"] = 39] = "IfcMechanicalFastener";
  IfcTypeEnum2[IfcTypeEnum2["IfcDistributionElement"] = 40] = "IfcDistributionElement";
  IfcTypeEnum2[IfcTypeEnum2["IfcFlowTerminal"] = 41] = "IfcFlowTerminal";
  IfcTypeEnum2[IfcTypeEnum2["IfcFlowSegment"] = 42] = "IfcFlowSegment";
  IfcTypeEnum2[IfcTypeEnum2["IfcFlowFitting"] = 43] = "IfcFlowFitting";
  IfcTypeEnum2[IfcTypeEnum2["IfcFlowController"] = 44] = "IfcFlowController";
  IfcTypeEnum2[IfcTypeEnum2["IfcFlowMovingDevice"] = 45] = "IfcFlowMovingDevice";
  IfcTypeEnum2[IfcTypeEnum2["IfcFlowStorageDevice"] = 46] = "IfcFlowStorageDevice";
  IfcTypeEnum2[IfcTypeEnum2["IfcFlowTreatmentDevice"] = 47] = "IfcFlowTreatmentDevice";
  IfcTypeEnum2[IfcTypeEnum2["IfcEnergyConversionDevice"] = 48] = "IfcEnergyConversionDevice";
  IfcTypeEnum2[IfcTypeEnum2["IfcDuctSegment"] = 49] = "IfcDuctSegment";
  IfcTypeEnum2[IfcTypeEnum2["IfcPipeSegment"] = 50] = "IfcPipeSegment";
  IfcTypeEnum2[IfcTypeEnum2["IfcCableSegment"] = 51] = "IfcCableSegment";
  IfcTypeEnum2[IfcTypeEnum2["IfcFurnishingElement"] = 52] = "IfcFurnishingElement";
  IfcTypeEnum2[IfcTypeEnum2["IfcFurniture"] = 53] = "IfcFurniture";
  IfcTypeEnum2[IfcTypeEnum2["IfcProxy"] = 54] = "IfcProxy";
  IfcTypeEnum2[IfcTypeEnum2["IfcAnnotation"] = 55] = "IfcAnnotation";
  IfcTypeEnum2[IfcTypeEnum2["IfcTransportElement"] = 56] = "IfcTransportElement";
  IfcTypeEnum2[IfcTypeEnum2["IfcCivilElement"] = 57] = "IfcCivilElement";
  IfcTypeEnum2[IfcTypeEnum2["IfcGeographicElement"] = 58] = "IfcGeographicElement";
  IfcTypeEnum2[IfcTypeEnum2["IfcRelContainedInSpatialStructure"] = 100] = "IfcRelContainedInSpatialStructure";
  IfcTypeEnum2[IfcTypeEnum2["IfcRelAggregates"] = 101] = "IfcRelAggregates";
  IfcTypeEnum2[IfcTypeEnum2["IfcRelDefinesByProperties"] = 102] = "IfcRelDefinesByProperties";
  IfcTypeEnum2[IfcTypeEnum2["IfcRelDefinesByType"] = 103] = "IfcRelDefinesByType";
  IfcTypeEnum2[IfcTypeEnum2["IfcRelAssociatesMaterial"] = 104] = "IfcRelAssociatesMaterial";
  IfcTypeEnum2[IfcTypeEnum2["IfcRelAssociatesClassification"] = 105] = "IfcRelAssociatesClassification";
  IfcTypeEnum2[IfcTypeEnum2["IfcRelVoidsElement"] = 106] = "IfcRelVoidsElement";
  IfcTypeEnum2[IfcTypeEnum2["IfcRelFillsElement"] = 107] = "IfcRelFillsElement";
  IfcTypeEnum2[IfcTypeEnum2["IfcRelConnectsPathElements"] = 108] = "IfcRelConnectsPathElements";
  IfcTypeEnum2[IfcTypeEnum2["IfcRelSpaceBoundary"] = 109] = "IfcRelSpaceBoundary";
  IfcTypeEnum2[IfcTypeEnum2["IfcPropertySet"] = 200] = "IfcPropertySet";
  IfcTypeEnum2[IfcTypeEnum2["IfcPropertySingleValue"] = 201] = "IfcPropertySingleValue";
  IfcTypeEnum2[IfcTypeEnum2["IfcPropertyEnumeratedValue"] = 202] = "IfcPropertyEnumeratedValue";
  IfcTypeEnum2[IfcTypeEnum2["IfcPropertyBoundedValue"] = 203] = "IfcPropertyBoundedValue";
  IfcTypeEnum2[IfcTypeEnum2["IfcPropertyListValue"] = 204] = "IfcPropertyListValue";
  IfcTypeEnum2[IfcTypeEnum2["IfcElementQuantity"] = 210] = "IfcElementQuantity";
  IfcTypeEnum2[IfcTypeEnum2["IfcQuantityLength"] = 211] = "IfcQuantityLength";
  IfcTypeEnum2[IfcTypeEnum2["IfcQuantityArea"] = 212] = "IfcQuantityArea";
  IfcTypeEnum2[IfcTypeEnum2["IfcQuantityVolume"] = 213] = "IfcQuantityVolume";
  IfcTypeEnum2[IfcTypeEnum2["IfcQuantityCount"] = 214] = "IfcQuantityCount";
  IfcTypeEnum2[IfcTypeEnum2["IfcQuantityWeight"] = 215] = "IfcQuantityWeight";
  IfcTypeEnum2[IfcTypeEnum2["IfcWallType"] = 300] = "IfcWallType";
  IfcTypeEnum2[IfcTypeEnum2["IfcDoorType"] = 301] = "IfcDoorType";
  IfcTypeEnum2[IfcTypeEnum2["IfcWindowType"] = 302] = "IfcWindowType";
  IfcTypeEnum2[IfcTypeEnum2["IfcSlabType"] = 303] = "IfcSlabType";
  IfcTypeEnum2[IfcTypeEnum2["IfcColumnType"] = 304] = "IfcColumnType";
  IfcTypeEnum2[IfcTypeEnum2["IfcBeamType"] = 305] = "IfcBeamType";
  IfcTypeEnum2[IfcTypeEnum2["IfcPileType"] = 306] = "IfcPileType";
  IfcTypeEnum2[IfcTypeEnum2["IfcMemberType"] = 307] = "IfcMemberType";
  IfcTypeEnum2[IfcTypeEnum2["IfcPlateType"] = 308] = "IfcPlateType";
  IfcTypeEnum2[IfcTypeEnum2["IfcFootingType"] = 309] = "IfcFootingType";
  IfcTypeEnum2[IfcTypeEnum2["IfcCoveringType"] = 310] = "IfcCoveringType";
  IfcTypeEnum2[IfcTypeEnum2["IfcRailingType"] = 311] = "IfcRailingType";
  IfcTypeEnum2[IfcTypeEnum2["IfcStairType"] = 312] = "IfcStairType";
  IfcTypeEnum2[IfcTypeEnum2["IfcRampType"] = 313] = "IfcRampType";
  IfcTypeEnum2[IfcTypeEnum2["IfcRoofType"] = 314] = "IfcRoofType";
  IfcTypeEnum2[IfcTypeEnum2["IfcCurtainWallType"] = 315] = "IfcCurtainWallType";
  IfcTypeEnum2[IfcTypeEnum2["IfcBuildingElementProxyType"] = 316] = "IfcBuildingElementProxyType";
  IfcTypeEnum2[IfcTypeEnum2["Unknown"] = 9999] = "Unknown";
})(IfcTypeEnum || (IfcTypeEnum = {}));
var PropertyValueType;
(function(PropertyValueType2) {
  PropertyValueType2[PropertyValueType2["String"] = 0] = "String";
  PropertyValueType2[PropertyValueType2["Real"] = 1] = "Real";
  PropertyValueType2[PropertyValueType2["Integer"] = 2] = "Integer";
  PropertyValueType2[PropertyValueType2["Boolean"] = 3] = "Boolean";
  PropertyValueType2[PropertyValueType2["Logical"] = 4] = "Logical";
  PropertyValueType2[PropertyValueType2["Label"] = 5] = "Label";
  PropertyValueType2[PropertyValueType2["Identifier"] = 6] = "Identifier";
  PropertyValueType2[PropertyValueType2["Text"] = 7] = "Text";
  PropertyValueType2[PropertyValueType2["Enum"] = 8] = "Enum";
  PropertyValueType2[PropertyValueType2["Reference"] = 9] = "Reference";
  PropertyValueType2[PropertyValueType2["List"] = 10] = "List";
})(PropertyValueType || (PropertyValueType = {}));
var QuantityType;
(function(QuantityType2) {
  QuantityType2[QuantityType2["Length"] = 0] = "Length";
  QuantityType2[QuantityType2["Area"] = 1] = "Area";
  QuantityType2[QuantityType2["Volume"] = 2] = "Volume";
  QuantityType2[QuantityType2["Count"] = 3] = "Count";
  QuantityType2[QuantityType2["Weight"] = 4] = "Weight";
  QuantityType2[QuantityType2["Time"] = 5] = "Time";
})(QuantityType || (QuantityType = {}));
var RelationshipType;
(function(RelationshipType2) {
  RelationshipType2[RelationshipType2["ContainsElements"] = 1] = "ContainsElements";
  RelationshipType2[RelationshipType2["Aggregates"] = 2] = "Aggregates";
  RelationshipType2[RelationshipType2["DefinesByProperties"] = 10] = "DefinesByProperties";
  RelationshipType2[RelationshipType2["DefinesByType"] = 11] = "DefinesByType";
  RelationshipType2[RelationshipType2["AssociatesMaterial"] = 20] = "AssociatesMaterial";
  RelationshipType2[RelationshipType2["AssociatesClassification"] = 30] = "AssociatesClassification";
  RelationshipType2[RelationshipType2["AssociatesDocument"] = 31] = "AssociatesDocument";
  RelationshipType2[RelationshipType2["ConnectsPathElements"] = 40] = "ConnectsPathElements";
  RelationshipType2[RelationshipType2["FillsElement"] = 41] = "FillsElement";
  RelationshipType2[RelationshipType2["VoidsElement"] = 42] = "VoidsElement";
  RelationshipType2[RelationshipType2["ConnectsElements"] = 43] = "ConnectsElements";
  RelationshipType2[RelationshipType2["SpaceBoundary"] = 50] = "SpaceBoundary";
  RelationshipType2[RelationshipType2["AssignsToGroup"] = 60] = "AssignsToGroup";
  RelationshipType2[RelationshipType2["AssignsToProduct"] = 61] = "AssignsToProduct";
  RelationshipType2[RelationshipType2["ReferencedInSpatialStructure"] = 70] = "ReferencedInSpatialStructure";
})(RelationshipType || (RelationshipType = {}));
var EntityFlags;
(function(EntityFlags2) {
  EntityFlags2[EntityFlags2["HAS_GEOMETRY"] = 1] = "HAS_GEOMETRY";
  EntityFlags2[EntityFlags2["HAS_PROPERTIES"] = 2] = "HAS_PROPERTIES";
  EntityFlags2[EntityFlags2["HAS_QUANTITIES"] = 4] = "HAS_QUANTITIES";
  EntityFlags2[EntityFlags2["IS_TYPE"] = 8] = "IS_TYPE";
  EntityFlags2[EntityFlags2["IS_EXTERNAL"] = 16] = "IS_EXTERNAL";
  EntityFlags2[EntityFlags2["HAS_OPENINGS"] = 32] = "HAS_OPENINGS";
  EntityFlags2[EntityFlags2["IS_FILLING"] = 64] = "IS_FILLING";
})(EntityFlags || (EntityFlags = {}));
var TYPE_STRING_TO_ENUM = /* @__PURE__ */ new Map([
  // Spatial
  ["IFCPROJECT", IfcTypeEnum.IfcProject],
  ["IFCSITE", IfcTypeEnum.IfcSite],
  ["IFCBUILDING", IfcTypeEnum.IfcBuilding],
  ["IFCBUILDINGSTOREY", IfcTypeEnum.IfcBuildingStorey],
  ["IFCSPACE", IfcTypeEnum.IfcSpace],
  ["IFCFACILITY", IfcTypeEnum.IfcFacility],
  ["IFCFACILITYPART", IfcTypeEnum.IfcFacilityPart],
  ["IFCBRIDGE", IfcTypeEnum.IfcBridge],
  ["IFCBRIDGEPART", IfcTypeEnum.IfcBridgePart],
  ["IFCROAD", IfcTypeEnum.IfcRoad],
  ["IFCROADPART", IfcTypeEnum.IfcRoadPart],
  ["IFCRAILWAY", IfcTypeEnum.IfcRailway],
  ["IFCRAILWAYPART", IfcTypeEnum.IfcRailwayPart],
  ["IFCMARINEFACILITY", IfcTypeEnum.IfcMarineFacility],
  // Building elements
  ["IFCWALL", IfcTypeEnum.IfcWall],
  ["IFCWALLSTANDARDCASE", IfcTypeEnum.IfcWallStandardCase],
  ["IFCDOOR", IfcTypeEnum.IfcDoor],
  ["IFCDOORSTANDARDCASE", IfcTypeEnum.IfcDoor],
  ["IFCWINDOW", IfcTypeEnum.IfcWindow],
  ["IFCWINDOWSTANDARDCASE", IfcTypeEnum.IfcWindow],
  ["IFCSLAB", IfcTypeEnum.IfcSlab],
  ["IFCSLABSTANDARDCASE", IfcTypeEnum.IfcSlab],
  ["IFCCOLUMN", IfcTypeEnum.IfcColumn],
  ["IFCCOLUMNSTANDARDCASE", IfcTypeEnum.IfcColumn],
  ["IFCBEAM", IfcTypeEnum.IfcBeam],
  ["IFCBEAMSTANDARDCASE", IfcTypeEnum.IfcBeam],
  ["IFCSTAIR", IfcTypeEnum.IfcStair],
  ["IFCSTAIRFLIGHT", IfcTypeEnum.IfcStairFlight],
  ["IFCRAMP", IfcTypeEnum.IfcRamp],
  ["IFCRAMPFLIGHT", IfcTypeEnum.IfcRampFlight],
  ["IFCROOF", IfcTypeEnum.IfcRoof],
  ["IFCCOVERING", IfcTypeEnum.IfcCovering],
  ["IFCCURTAINWALL", IfcTypeEnum.IfcCurtainWall],
  ["IFCRAILING", IfcTypeEnum.IfcRailing],
  ["IFCPILE", IfcTypeEnum.IfcPile],
  ["IFCMEMBER", IfcTypeEnum.IfcMember],
  ["IFCMEMBERSTANDARDCASE", IfcTypeEnum.IfcMember],
  ["IFCPLATE", IfcTypeEnum.IfcPlate],
  ["IFCPLATESTANDARDCASE", IfcTypeEnum.IfcPlate],
  ["IFCFOOTING", IfcTypeEnum.IfcFooting],
  ["IFCBUILDINGELEMENTPROXY", IfcTypeEnum.IfcBuildingElementProxy],
  ["IFCCHIMNEY", IfcTypeEnum.IfcChimney],
  ["IFCSHADINGDEVICE", IfcTypeEnum.IfcShadingDevice],
  ["IFCBUILDINGELEMENTPART", IfcTypeEnum.IfcBuildingElementPart],
  // Openings
  ["IFCOPENINGELEMENT", IfcTypeEnum.IfcOpeningElement],
  ["IFCOPENINGSTANDARDCASE", IfcTypeEnum.IfcOpeningElement],
  // Assemblies and structural
  ["IFCELEMENTASSEMBLY", IfcTypeEnum.IfcElementAssembly],
  ["IFCREINFORCINGBAR", IfcTypeEnum.IfcReinforcingBar],
  ["IFCREINFORCINGMESH", IfcTypeEnum.IfcReinforcingMesh],
  ["IFCTENDON", IfcTypeEnum.IfcTendon],
  ["IFCTENDONANCHOR", IfcTypeEnum.IfcTendon],
  ["IFCDISCRETEACCESSORY", IfcTypeEnum.IfcDiscreteAccessory],
  ["IFCMECHANICALFASTENER", IfcTypeEnum.IfcMechanicalFastener],
  ["IFCFASTENER", IfcTypeEnum.IfcMechanicalFastener],
  // MEP
  ["IFCDISTRIBUTIONELEMENT", IfcTypeEnum.IfcDistributionElement],
  ["IFCDISTRIBUTIONFLOWELEMENT", IfcTypeEnum.IfcDistributionElement],
  ["IFCDISTRIBUTIONCONTROLELEMENT", IfcTypeEnum.IfcDistributionElement],
  ["IFCFLOWTERMINAL", IfcTypeEnum.IfcFlowTerminal],
  ["IFCFLOWSEGMENT", IfcTypeEnum.IfcFlowSegment],
  ["IFCFLOWFITTING", IfcTypeEnum.IfcFlowFitting],
  ["IFCFLOWCONTROLLER", IfcTypeEnum.IfcFlowController],
  ["IFCFLOWMOVINGDEVICE", IfcTypeEnum.IfcFlowMovingDevice],
  ["IFCFLOWSTORAGEDEVICE", IfcTypeEnum.IfcFlowStorageDevice],
  ["IFCFLOWTREATMENTDEVICE", IfcTypeEnum.IfcFlowTreatmentDevice],
  ["IFCENERGYCONVERSIONDEVICE", IfcTypeEnum.IfcEnergyConversionDevice],
  ["IFCDUCTSEGMENT", IfcTypeEnum.IfcDuctSegment],
  ["IFCPIPESEGMENT", IfcTypeEnum.IfcPipeSegment],
  ["IFCCABLESEGMENT", IfcTypeEnum.IfcCableSegment],
  ["IFCCABLECARRIERSEGMENT", IfcTypeEnum.IfcCableSegment],
  // Furnishing
  ["IFCFURNISHINGELEMENT", IfcTypeEnum.IfcFurnishingElement],
  ["IFCFURNITURE", IfcTypeEnum.IfcFurniture],
  // Other products
  ["IFCPROXY", IfcTypeEnum.IfcProxy],
  ["IFCANNOTATION", IfcTypeEnum.IfcAnnotation],
  ["IFCTRANSPORTELEMENT", IfcTypeEnum.IfcTransportElement],
  ["IFCCIVILELEMENT", IfcTypeEnum.IfcCivilElement],
  ["IFCGEOGRAPHICELEMENT", IfcTypeEnum.IfcGeographicElement],
  // Relationships
  ["IFCRELCONTAINEDINSPATIALSTRUCTURE", IfcTypeEnum.IfcRelContainedInSpatialStructure],
  ["IFCRELAGGREGATES", IfcTypeEnum.IfcRelAggregates],
  ["IFCRELDEFINESBYPROPERTIES", IfcTypeEnum.IfcRelDefinesByProperties],
  ["IFCRELDEFINESBYTYPE", IfcTypeEnum.IfcRelDefinesByType],
  ["IFCRELASSOCIATESMATERIAL", IfcTypeEnum.IfcRelAssociatesMaterial],
  ["IFCRELASSOCIATESCLASSIFICATION", IfcTypeEnum.IfcRelAssociatesClassification],
  ["IFCRELVOIDSELEMENT", IfcTypeEnum.IfcRelVoidsElement],
  ["IFCRELFILLSELEMENT", IfcTypeEnum.IfcRelFillsElement],
  ["IFCRELCONNECTSPATHELEMENTS", IfcTypeEnum.IfcRelConnectsPathElements],
  ["IFCRELSPACEBOUNDARY", IfcTypeEnum.IfcRelSpaceBoundary],
  // Properties
  ["IFCPROPERTYSET", IfcTypeEnum.IfcPropertySet],
  ["IFCPROPERTYSINGLEVALUE", IfcTypeEnum.IfcPropertySingleValue],
  ["IFCPROPERTYENUMERATEDVALUE", IfcTypeEnum.IfcPropertyEnumeratedValue],
  ["IFCPROPERTYBOUNDEDVALUE", IfcTypeEnum.IfcPropertyBoundedValue],
  ["IFCPROPERTYLISTVALUE", IfcTypeEnum.IfcPropertyListValue],
  ["IFCELEMENTQUANTITY", IfcTypeEnum.IfcElementQuantity],
  ["IFCQUANTITYLENGTH", IfcTypeEnum.IfcQuantityLength],
  ["IFCQUANTITYAREA", IfcTypeEnum.IfcQuantityArea],
  ["IFCQUANTITYVOLUME", IfcTypeEnum.IfcQuantityVolume],
  ["IFCQUANTITYCOUNT", IfcTypeEnum.IfcQuantityCount],
  ["IFCQUANTITYWEIGHT", IfcTypeEnum.IfcQuantityWeight],
  // Type definitions
  ["IFCWALLTYPE", IfcTypeEnum.IfcWallType],
  ["IFCDOORTYPE", IfcTypeEnum.IfcDoorType],
  ["IFCWINDOWTYPE", IfcTypeEnum.IfcWindowType],
  ["IFCSLABTYPE", IfcTypeEnum.IfcSlabType],
  ["IFCCOLUMNTYPE", IfcTypeEnum.IfcColumnType],
  ["IFCBEAMTYPE", IfcTypeEnum.IfcBeamType],
  ["IFCPILETYPE", IfcTypeEnum.IfcPileType],
  ["IFCMEMBERTYPE", IfcTypeEnum.IfcMemberType],
  ["IFCPLATETYPE", IfcTypeEnum.IfcPlateType],
  ["IFCFOOTINGTYPE", IfcTypeEnum.IfcFootingType],
  ["IFCCOVERINGTYPE", IfcTypeEnum.IfcCoveringType],
  ["IFCRAILINGTYPE", IfcTypeEnum.IfcRailingType],
  ["IFCSTAIRTYPE", IfcTypeEnum.IfcStairType],
  ["IFCRAMPTYPE", IfcTypeEnum.IfcRampType],
  ["IFCROOFTYPE", IfcTypeEnum.IfcRoofType],
  ["IFCCURTAINWALLTYPE", IfcTypeEnum.IfcCurtainWallType],
  ["IFCBUILDINGELEMENTPROXYTYPE", IfcTypeEnum.IfcBuildingElementProxyType]
]);
var TYPE_ENUM_TO_STRING = /* @__PURE__ */ new Map([
  // Spatial
  [IfcTypeEnum.IfcProject, "IfcProject"],
  [IfcTypeEnum.IfcSite, "IfcSite"],
  [IfcTypeEnum.IfcBuilding, "IfcBuilding"],
  [IfcTypeEnum.IfcBuildingStorey, "IfcBuildingStorey"],
  [IfcTypeEnum.IfcSpace, "IfcSpace"],
  [IfcTypeEnum.IfcFacility, "IfcFacility"],
  [IfcTypeEnum.IfcFacilityPart, "IfcFacilityPart"],
  [IfcTypeEnum.IfcBridge, "IfcBridge"],
  [IfcTypeEnum.IfcBridgePart, "IfcBridgePart"],
  [IfcTypeEnum.IfcRoad, "IfcRoad"],
  [IfcTypeEnum.IfcRoadPart, "IfcRoadPart"],
  [IfcTypeEnum.IfcRailway, "IfcRailway"],
  [IfcTypeEnum.IfcRailwayPart, "IfcRailwayPart"],
  [IfcTypeEnum.IfcMarineFacility, "IfcMarineFacility"],
  // Building elements
  [IfcTypeEnum.IfcWall, "IfcWall"],
  [IfcTypeEnum.IfcWallStandardCase, "IfcWallStandardCase"],
  [IfcTypeEnum.IfcDoor, "IfcDoor"],
  [IfcTypeEnum.IfcWindow, "IfcWindow"],
  [IfcTypeEnum.IfcSlab, "IfcSlab"],
  [IfcTypeEnum.IfcColumn, "IfcColumn"],
  [IfcTypeEnum.IfcBeam, "IfcBeam"],
  [IfcTypeEnum.IfcStair, "IfcStair"],
  [IfcTypeEnum.IfcStairFlight, "IfcStairFlight"],
  [IfcTypeEnum.IfcRamp, "IfcRamp"],
  [IfcTypeEnum.IfcRampFlight, "IfcRampFlight"],
  [IfcTypeEnum.IfcRoof, "IfcRoof"],
  [IfcTypeEnum.IfcCovering, "IfcCovering"],
  [IfcTypeEnum.IfcCurtainWall, "IfcCurtainWall"],
  [IfcTypeEnum.IfcRailing, "IfcRailing"],
  [IfcTypeEnum.IfcPile, "IfcPile"],
  [IfcTypeEnum.IfcMember, "IfcMember"],
  [IfcTypeEnum.IfcPlate, "IfcPlate"],
  [IfcTypeEnum.IfcFooting, "IfcFooting"],
  [IfcTypeEnum.IfcBuildingElementProxy, "IfcBuildingElementProxy"],
  [IfcTypeEnum.IfcChimney, "IfcChimney"],
  [IfcTypeEnum.IfcShadingDevice, "IfcShadingDevice"],
  [IfcTypeEnum.IfcBuildingElementPart, "IfcBuildingElementPart"],
  // Openings
  [IfcTypeEnum.IfcOpeningElement, "IfcOpeningElement"],
  // Assemblies and structural
  [IfcTypeEnum.IfcElementAssembly, "IfcElementAssembly"],
  [IfcTypeEnum.IfcReinforcingBar, "IfcReinforcingBar"],
  [IfcTypeEnum.IfcReinforcingMesh, "IfcReinforcingMesh"],
  [IfcTypeEnum.IfcTendon, "IfcTendon"],
  [IfcTypeEnum.IfcDiscreteAccessory, "IfcDiscreteAccessory"],
  [IfcTypeEnum.IfcMechanicalFastener, "IfcMechanicalFastener"],
  // MEP
  [IfcTypeEnum.IfcDistributionElement, "IfcDistributionElement"],
  [IfcTypeEnum.IfcFlowTerminal, "IfcFlowTerminal"],
  [IfcTypeEnum.IfcFlowSegment, "IfcFlowSegment"],
  [IfcTypeEnum.IfcFlowFitting, "IfcFlowFitting"],
  [IfcTypeEnum.IfcFlowController, "IfcFlowController"],
  [IfcTypeEnum.IfcFlowMovingDevice, "IfcFlowMovingDevice"],
  [IfcTypeEnum.IfcFlowStorageDevice, "IfcFlowStorageDevice"],
  [IfcTypeEnum.IfcFlowTreatmentDevice, "IfcFlowTreatmentDevice"],
  [IfcTypeEnum.IfcEnergyConversionDevice, "IfcEnergyConversionDevice"],
  [IfcTypeEnum.IfcDuctSegment, "IfcDuctSegment"],
  [IfcTypeEnum.IfcPipeSegment, "IfcPipeSegment"],
  [IfcTypeEnum.IfcCableSegment, "IfcCableSegment"],
  // Furnishing
  [IfcTypeEnum.IfcFurnishingElement, "IfcFurnishingElement"],
  [IfcTypeEnum.IfcFurniture, "IfcFurniture"],
  // Other products
  [IfcTypeEnum.IfcProxy, "IfcProxy"],
  [IfcTypeEnum.IfcAnnotation, "IfcAnnotation"],
  [IfcTypeEnum.IfcTransportElement, "IfcTransportElement"],
  [IfcTypeEnum.IfcCivilElement, "IfcCivilElement"],
  [IfcTypeEnum.IfcGeographicElement, "IfcGeographicElement"],
  // Relationships
  [IfcTypeEnum.IfcRelContainedInSpatialStructure, "IfcRelContainedInSpatialStructure"],
  [IfcTypeEnum.IfcRelAggregates, "IfcRelAggregates"],
  [IfcTypeEnum.IfcRelDefinesByProperties, "IfcRelDefinesByProperties"],
  [IfcTypeEnum.IfcRelDefinesByType, "IfcRelDefinesByType"],
  [IfcTypeEnum.IfcRelAssociatesMaterial, "IfcRelAssociatesMaterial"],
  [IfcTypeEnum.IfcRelAssociatesClassification, "IfcRelAssociatesClassification"],
  [IfcTypeEnum.IfcRelVoidsElement, "IfcRelVoidsElement"],
  [IfcTypeEnum.IfcRelFillsElement, "IfcRelFillsElement"],
  [IfcTypeEnum.IfcRelConnectsPathElements, "IfcRelConnectsPathElements"],
  [IfcTypeEnum.IfcRelSpaceBoundary, "IfcRelSpaceBoundary"],
  // Properties
  [IfcTypeEnum.IfcPropertySet, "IfcPropertySet"],
  [IfcTypeEnum.IfcPropertySingleValue, "IfcPropertySingleValue"],
  [IfcTypeEnum.IfcPropertyEnumeratedValue, "IfcPropertyEnumeratedValue"],
  [IfcTypeEnum.IfcPropertyBoundedValue, "IfcPropertyBoundedValue"],
  [IfcTypeEnum.IfcPropertyListValue, "IfcPropertyListValue"],
  [IfcTypeEnum.IfcElementQuantity, "IfcElementQuantity"],
  [IfcTypeEnum.IfcQuantityLength, "IfcQuantityLength"],
  [IfcTypeEnum.IfcQuantityArea, "IfcQuantityArea"],
  [IfcTypeEnum.IfcQuantityVolume, "IfcQuantityVolume"],
  [IfcTypeEnum.IfcQuantityCount, "IfcQuantityCount"],
  [IfcTypeEnum.IfcQuantityWeight, "IfcQuantityWeight"],
  // Type definitions
  [IfcTypeEnum.IfcWallType, "IfcWallType"],
  [IfcTypeEnum.IfcDoorType, "IfcDoorType"],
  [IfcTypeEnum.IfcWindowType, "IfcWindowType"],
  [IfcTypeEnum.IfcSlabType, "IfcSlabType"],
  [IfcTypeEnum.IfcColumnType, "IfcColumnType"],
  [IfcTypeEnum.IfcBeamType, "IfcBeamType"],
  [IfcTypeEnum.IfcPileType, "IfcPileType"],
  [IfcTypeEnum.IfcMemberType, "IfcMemberType"],
  [IfcTypeEnum.IfcPlateType, "IfcPlateType"],
  [IfcTypeEnum.IfcFootingType, "IfcFootingType"],
  [IfcTypeEnum.IfcCoveringType, "IfcCoveringType"],
  [IfcTypeEnum.IfcRailingType, "IfcRailingType"],
  [IfcTypeEnum.IfcStairType, "IfcStairType"],
  [IfcTypeEnum.IfcRampType, "IfcRampType"],
  [IfcTypeEnum.IfcRoofType, "IfcRoofType"],
  [IfcTypeEnum.IfcCurtainWallType, "IfcCurtainWallType"],
  [IfcTypeEnum.IfcBuildingElementProxyType, "IfcBuildingElementProxyType"]
]);
function IfcTypeEnumFromString(str) {
  return TYPE_STRING_TO_ENUM.get(str.toUpperCase()) ?? IfcTypeEnum.Unknown;
}
function IfcTypeEnumToString(type) {
  return TYPE_ENUM_TO_STRING.get(type) ?? "Unknown";
}

// viewer/node_modules/@ifc-lite/data/dist/ifc-entity-names.js
var IFC_ENTITY_NAMES = {
  "IFCACTIONREQUEST": "IfcActionRequest",
  "IFCACTOR": "IfcActor",
  "IFCACTORROLE": "IfcActorRole",
  "IFCACTUATOR": "IfcActuator",
  "IFCACTUATORTYPE": "IfcActuatorType",
  "IFCADDRESS": "IfcAddress",
  "IFCADVANCEDBREP": "IfcAdvancedBrep",
  "IFCADVANCEDBREPWITHVOIDS": "IfcAdvancedBrepWithVoids",
  "IFCADVANCEDFACE": "IfcAdvancedFace",
  "IFCAIRTERMINAL": "IfcAirTerminal",
  "IFCAIRTERMINALBOX": "IfcAirTerminalBox",
  "IFCAIRTERMINALBOXTYPE": "IfcAirTerminalBoxType",
  "IFCAIRTERMINALTYPE": "IfcAirTerminalType",
  "IFCAIRTOAIRHEATRECOVERY": "IfcAirToAirHeatRecovery",
  "IFCAIRTOAIRHEATRECOVERYTYPE": "IfcAirToAirHeatRecoveryType",
  "IFCALARM": "IfcAlarm",
  "IFCALARMTYPE": "IfcAlarmType",
  "IFCALIGNMENT": "IfcAlignment",
  "IFCALIGNMENTCANT": "IfcAlignmentCant",
  "IFCALIGNMENTCANTSEGMENT": "IfcAlignmentCantSegment",
  "IFCALIGNMENTHORIZONTAL": "IfcAlignmentHorizontal",
  "IFCALIGNMENTHORIZONTALSEGMENT": "IfcAlignmentHorizontalSegment",
  "IFCALIGNMENTPARAMETERSEGMENT": "IfcAlignmentParameterSegment",
  "IFCALIGNMENTSEGMENT": "IfcAlignmentSegment",
  "IFCALIGNMENTVERTICAL": "IfcAlignmentVertical",
  "IFCALIGNMENTVERTICALSEGMENT": "IfcAlignmentVerticalSegment",
  "IFCANNOTATION": "IfcAnnotation",
  "IFCANNOTATIONFILLAREA": "IfcAnnotationFillArea",
  "IFCAPPLICATION": "IfcApplication",
  "IFCAPPLIEDVALUE": "IfcAppliedValue",
  "IFCAPPROVAL": "IfcApproval",
  "IFCAPPROVALRELATIONSHIP": "IfcApprovalRelationship",
  "IFCARBITRARYCLOSEDPROFILEDEF": "IfcArbitraryClosedProfileDef",
  "IFCARBITRARYOPENPROFILEDEF": "IfcArbitraryOpenProfileDef",
  "IFCARBITRARYPROFILEDEFWITHVOIDS": "IfcArbitraryProfileDefWithVoids",
  "IFCASSET": "IfcAsset",
  "IFCASYMMETRICISHAPEPROFILEDEF": "IfcAsymmetricIShapeProfileDef",
  "IFCAUDIOVISUALAPPLIANCE": "IfcAudioVisualAppliance",
  "IFCAUDIOVISUALAPPLIANCETYPE": "IfcAudioVisualApplianceType",
  "IFCAXIS1PLACEMENT": "IfcAxis1Placement",
  "IFCAXIS2PLACEMENT2D": "IfcAxis2Placement2D",
  "IFCAXIS2PLACEMENT3D": "IfcAxis2Placement3D",
  "IFCAXIS2PLACEMENTLINEAR": "IfcAxis2PlacementLinear",
  "IFCBSPLINECURVE": "IfcBSplineCurve",
  "IFCBSPLINECURVEWITHKNOTS": "IfcBSplineCurveWithKnots",
  "IFCBSPLINESURFACE": "IfcBSplineSurface",
  "IFCBSPLINESURFACEWITHKNOTS": "IfcBSplineSurfaceWithKnots",
  "IFCBEAM": "IfcBeam",
  "IFCBEAMTYPE": "IfcBeamType",
  "IFCBEARING": "IfcBearing",
  "IFCBEARINGTYPE": "IfcBearingType",
  "IFCBLOBTEXTURE": "IfcBlobTexture",
  "IFCBLOCK": "IfcBlock",
  "IFCBOILER": "IfcBoiler",
  "IFCBOILERTYPE": "IfcBoilerType",
  "IFCBOOLEANCLIPPINGRESULT": "IfcBooleanClippingResult",
  "IFCBOOLEANRESULT": "IfcBooleanResult",
  "IFCBOREHOLE": "IfcBorehole",
  "IFCBOUNDARYCONDITION": "IfcBoundaryCondition",
  "IFCBOUNDARYCURVE": "IfcBoundaryCurve",
  "IFCBOUNDARYEDGECONDITION": "IfcBoundaryEdgeCondition",
  "IFCBOUNDARYFACECONDITION": "IfcBoundaryFaceCondition",
  "IFCBOUNDARYNODECONDITION": "IfcBoundaryNodeCondition",
  "IFCBOUNDARYNODECONDITIONWARPING": "IfcBoundaryNodeConditionWarping",
  "IFCBOUNDEDCURVE": "IfcBoundedCurve",
  "IFCBOUNDEDSURFACE": "IfcBoundedSurface",
  "IFCBOUNDINGBOX": "IfcBoundingBox",
  "IFCBOXEDHALFSPACE": "IfcBoxedHalfSpace",
  "IFCBRIDGE": "IfcBridge",
  "IFCBRIDGEPART": "IfcBridgePart",
  "IFCBUILDING": "IfcBuilding",
  "IFCBUILDINGELEMENTPART": "IfcBuildingElementPart",
  "IFCBUILDINGELEMENTPARTTYPE": "IfcBuildingElementPartType",
  "IFCBUILDINGELEMENTPROXY": "IfcBuildingElementProxy",
  "IFCBUILDINGELEMENTPROXYTYPE": "IfcBuildingElementProxyType",
  "IFCBUILDINGSTOREY": "IfcBuildingStorey",
  "IFCBUILDINGSYSTEM": "IfcBuildingSystem",
  "IFCBUILTELEMENT": "IfcBuiltElement",
  "IFCBUILTELEMENTTYPE": "IfcBuiltElementType",
  "IFCBUILTSYSTEM": "IfcBuiltSystem",
  "IFCBURNER": "IfcBurner",
  "IFCBURNERTYPE": "IfcBurnerType",
  "IFCCSHAPEPROFILEDEF": "IfcCShapeProfileDef",
  "IFCCABLECARRIERFITTING": "IfcCableCarrierFitting",
  "IFCCABLECARRIERFITTINGTYPE": "IfcCableCarrierFittingType",
  "IFCCABLECARRIERSEGMENT": "IfcCableCarrierSegment",
  "IFCCABLECARRIERSEGMENTTYPE": "IfcCableCarrierSegmentType",
  "IFCCABLEFITTING": "IfcCableFitting",
  "IFCCABLEFITTINGTYPE": "IfcCableFittingType",
  "IFCCABLESEGMENT": "IfcCableSegment",
  "IFCCABLESEGMENTTYPE": "IfcCableSegmentType",
  "IFCCAISSONFOUNDATION": "IfcCaissonFoundation",
  "IFCCAISSONFOUNDATIONTYPE": "IfcCaissonFoundationType",
  "IFCCARTESIANPOINT": "IfcCartesianPoint",
  "IFCCARTESIANPOINTLIST": "IfcCartesianPointList",
  "IFCCARTESIANPOINTLIST2D": "IfcCartesianPointList2D",
  "IFCCARTESIANPOINTLIST3D": "IfcCartesianPointList3D",
  "IFCCARTESIANTRANSFORMATIONOPERATOR": "IfcCartesianTransformationOperator",
  "IFCCARTESIANTRANSFORMATIONOPERATOR2D": "IfcCartesianTransformationOperator2D",
  "IFCCARTESIANTRANSFORMATIONOPERATOR2DNONUNIFORM": "IfcCartesianTransformationOperator2DnonUniform",
  "IFCCARTESIANTRANSFORMATIONOPERATOR3D": "IfcCartesianTransformationOperator3D",
  "IFCCARTESIANTRANSFORMATIONOPERATOR3DNONUNIFORM": "IfcCartesianTransformationOperator3DnonUniform",
  "IFCCENTERLINEPROFILEDEF": "IfcCenterLineProfileDef",
  "IFCCHILLER": "IfcChiller",
  "IFCCHILLERTYPE": "IfcChillerType",
  "IFCCHIMNEY": "IfcChimney",
  "IFCCHIMNEYTYPE": "IfcChimneyType",
  "IFCCIRCLE": "IfcCircle",
  "IFCCIRCLEHOLLOWPROFILEDEF": "IfcCircleHollowProfileDef",
  "IFCCIRCLEPROFILEDEF": "IfcCircleProfileDef",
  "IFCCIVILELEMENT": "IfcCivilElement",
  "IFCCIVILELEMENTTYPE": "IfcCivilElementType",
  "IFCCLASSIFICATION": "IfcClassification",
  "IFCCLASSIFICATIONREFERENCE": "IfcClassificationReference",
  "IFCCLOSEDSHELL": "IfcClosedShell",
  "IFCCLOTHOID": "IfcClothoid",
  "IFCCOIL": "IfcCoil",
  "IFCCOILTYPE": "IfcCoilType",
  "IFCCOLOURRGB": "IfcColourRgb",
  "IFCCOLOURRGBLIST": "IfcColourRgbList",
  "IFCCOLOURSPECIFICATION": "IfcColourSpecification",
  "IFCCOLUMN": "IfcColumn",
  "IFCCOLUMNTYPE": "IfcColumnType",
  "IFCCOMMUNICATIONSAPPLIANCE": "IfcCommunicationsAppliance",
  "IFCCOMMUNICATIONSAPPLIANCETYPE": "IfcCommunicationsApplianceType",
  "IFCCOMPLEXPROPERTY": "IfcComplexProperty",
  "IFCCOMPLEXPROPERTYTEMPLATE": "IfcComplexPropertyTemplate",
  "IFCCOMPOSITECURVE": "IfcCompositeCurve",
  "IFCCOMPOSITECURVEONSURFACE": "IfcCompositeCurveOnSurface",
  "IFCCOMPOSITECURVESEGMENT": "IfcCompositeCurveSegment",
  "IFCCOMPOSITEPROFILEDEF": "IfcCompositeProfileDef",
  "IFCCOMPRESSOR": "IfcCompressor",
  "IFCCOMPRESSORTYPE": "IfcCompressorType",
  "IFCCONDENSER": "IfcCondenser",
  "IFCCONDENSERTYPE": "IfcCondenserType",
  "IFCCONIC": "IfcConic",
  "IFCCONNECTEDFACESET": "IfcConnectedFaceSet",
  "IFCCONNECTIONCURVEGEOMETRY": "IfcConnectionCurveGeometry",
  "IFCCONNECTIONGEOMETRY": "IfcConnectionGeometry",
  "IFCCONNECTIONPOINTECCENTRICITY": "IfcConnectionPointEccentricity",
  "IFCCONNECTIONPOINTGEOMETRY": "IfcConnectionPointGeometry",
  "IFCCONNECTIONSURFACEGEOMETRY": "IfcConnectionSurfaceGeometry",
  "IFCCONNECTIONVOLUMEGEOMETRY": "IfcConnectionVolumeGeometry",
  "IFCCONSTRAINT": "IfcConstraint",
  "IFCCONSTRUCTIONEQUIPMENTRESOURCE": "IfcConstructionEquipmentResource",
  "IFCCONSTRUCTIONEQUIPMENTRESOURCETYPE": "IfcConstructionEquipmentResourceType",
  "IFCCONSTRUCTIONMATERIALRESOURCE": "IfcConstructionMaterialResource",
  "IFCCONSTRUCTIONMATERIALRESOURCETYPE": "IfcConstructionMaterialResourceType",
  "IFCCONSTRUCTIONPRODUCTRESOURCE": "IfcConstructionProductResource",
  "IFCCONSTRUCTIONPRODUCTRESOURCETYPE": "IfcConstructionProductResourceType",
  "IFCCONSTRUCTIONRESOURCE": "IfcConstructionResource",
  "IFCCONSTRUCTIONRESOURCETYPE": "IfcConstructionResourceType",
  "IFCCONTEXT": "IfcContext",
  "IFCCONTEXTDEPENDENTUNIT": "IfcContextDependentUnit",
  "IFCCONTROL": "IfcControl",
  "IFCCONTROLLER": "IfcController",
  "IFCCONTROLLERTYPE": "IfcControllerType",
  "IFCCONVERSIONBASEDUNIT": "IfcConversionBasedUnit",
  "IFCCONVERSIONBASEDUNITWITHOFFSET": "IfcConversionBasedUnitWithOffset",
  "IFCCONVEYORSEGMENT": "IfcConveyorSegment",
  "IFCCONVEYORSEGMENTTYPE": "IfcConveyorSegmentType",
  "IFCCOOLEDBEAM": "IfcCooledBeam",
  "IFCCOOLEDBEAMTYPE": "IfcCooledBeamType",
  "IFCCOOLINGTOWER": "IfcCoolingTower",
  "IFCCOOLINGTOWERTYPE": "IfcCoolingTowerType",
  "IFCCOORDINATEOPERATION": "IfcCoordinateOperation",
  "IFCCOORDINATEREFERENCESYSTEM": "IfcCoordinateReferenceSystem",
  "IFCCOSINESPIRAL": "IfcCosineSpiral",
  "IFCCOSTITEM": "IfcCostItem",
  "IFCCOSTSCHEDULE": "IfcCostSchedule",
  "IFCCOSTVALUE": "IfcCostValue",
  "IFCCOURSE": "IfcCourse",
  "IFCCOURSETYPE": "IfcCourseType",
  "IFCCOVERING": "IfcCovering",
  "IFCCOVERINGTYPE": "IfcCoveringType",
  "IFCCREWRESOURCE": "IfcCrewResource",
  "IFCCREWRESOURCETYPE": "IfcCrewResourceType",
  "IFCCSGPRIMITIVE3D": "IfcCsgPrimitive3D",
  "IFCCSGSOLID": "IfcCsgSolid",
  "IFCCURRENCYRELATIONSHIP": "IfcCurrencyRelationship",
  "IFCCURTAINWALL": "IfcCurtainWall",
  "IFCCURTAINWALLTYPE": "IfcCurtainWallType",
  "IFCCURVE": "IfcCurve",
  "IFCCURVEBOUNDEDPLANE": "IfcCurveBoundedPlane",
  "IFCCURVEBOUNDEDSURFACE": "IfcCurveBoundedSurface",
  "IFCCURVESEGMENT": "IfcCurveSegment",
  "IFCCURVESTYLE": "IfcCurveStyle",
  "IFCCURVESTYLEFONT": "IfcCurveStyleFont",
  "IFCCURVESTYLEFONTANDSCALING": "IfcCurveStyleFontAndScaling",
  "IFCCURVESTYLEFONTPATTERN": "IfcCurveStyleFontPattern",
  "IFCCYLINDRICALSURFACE": "IfcCylindricalSurface",
  "IFCDAMPER": "IfcDamper",
  "IFCDAMPERTYPE": "IfcDamperType",
  "IFCDEEPFOUNDATION": "IfcDeepFoundation",
  "IFCDEEPFOUNDATIONTYPE": "IfcDeepFoundationType",
  "IFCDERIVEDPROFILEDEF": "IfcDerivedProfileDef",
  "IFCDERIVEDUNIT": "IfcDerivedUnit",
  "IFCDERIVEDUNITELEMENT": "IfcDerivedUnitElement",
  "IFCDIMENSIONALEXPONENTS": "IfcDimensionalExponents",
  "IFCDIRECTION": "IfcDirection",
  "IFCDIRECTRIXCURVESWEPTAREASOLID": "IfcDirectrixCurveSweptAreaSolid",
  "IFCDIRECTRIXDERIVEDREFERENCESWEPTAREASOLID": "IfcDirectrixDerivedReferenceSweptAreaSolid",
  "IFCDISCRETEACCESSORY": "IfcDiscreteAccessory",
  "IFCDISCRETEACCESSORYTYPE": "IfcDiscreteAccessoryType",
  "IFCDISTRIBUTIONBOARD": "IfcDistributionBoard",
  "IFCDISTRIBUTIONBOARDTYPE": "IfcDistributionBoardType",
  "IFCDISTRIBUTIONCHAMBERELEMENT": "IfcDistributionChamberElement",
  "IFCDISTRIBUTIONCHAMBERELEMENTTYPE": "IfcDistributionChamberElementType",
  "IFCDISTRIBUTIONCIRCUIT": "IfcDistributionCircuit",
  "IFCDISTRIBUTIONCONTROLELEMENT": "IfcDistributionControlElement",
  "IFCDISTRIBUTIONCONTROLELEMENTTYPE": "IfcDistributionControlElementType",
  "IFCDISTRIBUTIONELEMENT": "IfcDistributionElement",
  "IFCDISTRIBUTIONELEMENTTYPE": "IfcDistributionElementType",
  "IFCDISTRIBUTIONFLOWELEMENT": "IfcDistributionFlowElement",
  "IFCDISTRIBUTIONFLOWELEMENTTYPE": "IfcDistributionFlowElementType",
  "IFCDISTRIBUTIONPORT": "IfcDistributionPort",
  "IFCDISTRIBUTIONSYSTEM": "IfcDistributionSystem",
  "IFCDOCUMENTINFORMATION": "IfcDocumentInformation",
  "IFCDOCUMENTINFORMATIONRELATIONSHIP": "IfcDocumentInformationRelationship",
  "IFCDOCUMENTREFERENCE": "IfcDocumentReference",
  "IFCDOOR": "IfcDoor",
  "IFCDOORLININGPROPERTIES": "IfcDoorLiningProperties",
  "IFCDOORPANELPROPERTIES": "IfcDoorPanelProperties",
  "IFCDOORTYPE": "IfcDoorType",
  "IFCDRAUGHTINGPREDEFINEDCOLOUR": "IfcDraughtingPreDefinedColour",
  "IFCDRAUGHTINGPREDEFINEDCURVEFONT": "IfcDraughtingPreDefinedCurveFont",
  "IFCDUCTFITTING": "IfcDuctFitting",
  "IFCDUCTFITTINGTYPE": "IfcDuctFittingType",
  "IFCDUCTSEGMENT": "IfcDuctSegment",
  "IFCDUCTSEGMENTTYPE": "IfcDuctSegmentType",
  "IFCDUCTSILENCER": "IfcDuctSilencer",
  "IFCDUCTSILENCERTYPE": "IfcDuctSilencerType",
  "IFCEARTHWORKSCUT": "IfcEarthworksCut",
  "IFCEARTHWORKSELEMENT": "IfcEarthworksElement",
  "IFCEARTHWORKSFILL": "IfcEarthworksFill",
  "IFCEDGE": "IfcEdge",
  "IFCEDGECURVE": "IfcEdgeCurve",
  "IFCEDGELOOP": "IfcEdgeLoop",
  "IFCELECTRICAPPLIANCE": "IfcElectricAppliance",
  "IFCELECTRICAPPLIANCETYPE": "IfcElectricApplianceType",
  "IFCELECTRICDISTRIBUTIONBOARD": "IfcElectricDistributionBoard",
  "IFCELECTRICDISTRIBUTIONBOARDTYPE": "IfcElectricDistributionBoardType",
  "IFCELECTRICFLOWSTORAGEDEVICE": "IfcElectricFlowStorageDevice",
  "IFCELECTRICFLOWSTORAGEDEVICETYPE": "IfcElectricFlowStorageDeviceType",
  "IFCELECTRICFLOWTREATMENTDEVICE": "IfcElectricFlowTreatmentDevice",
  "IFCELECTRICFLOWTREATMENTDEVICETYPE": "IfcElectricFlowTreatmentDeviceType",
  "IFCELECTRICGENERATOR": "IfcElectricGenerator",
  "IFCELECTRICGENERATORTYPE": "IfcElectricGeneratorType",
  "IFCELECTRICMOTOR": "IfcElectricMotor",
  "IFCELECTRICMOTORTYPE": "IfcElectricMotorType",
  "IFCELECTRICTIMECONTROL": "IfcElectricTimeControl",
  "IFCELECTRICTIMECONTROLTYPE": "IfcElectricTimeControlType",
  "IFCELEMENT": "IfcElement",
  "IFCELEMENTASSEMBLY": "IfcElementAssembly",
  "IFCELEMENTASSEMBLYTYPE": "IfcElementAssemblyType",
  "IFCELEMENTCOMPONENT": "IfcElementComponent",
  "IFCELEMENTCOMPONENTTYPE": "IfcElementComponentType",
  "IFCELEMENTQUANTITY": "IfcElementQuantity",
  "IFCELEMENTTYPE": "IfcElementType",
  "IFCELEMENTARYSURFACE": "IfcElementarySurface",
  "IFCELLIPSE": "IfcEllipse",
  "IFCELLIPSEPROFILEDEF": "IfcEllipseProfileDef",
  "IFCENERGYCONVERSIONDEVICE": "IfcEnergyConversionDevice",
  "IFCENERGYCONVERSIONDEVICETYPE": "IfcEnergyConversionDeviceType",
  "IFCENGINE": "IfcEngine",
  "IFCENGINETYPE": "IfcEngineType",
  "IFCEVAPORATIVECOOLER": "IfcEvaporativeCooler",
  "IFCEVAPORATIVECOOLERTYPE": "IfcEvaporativeCoolerType",
  "IFCEVAPORATOR": "IfcEvaporator",
  "IFCEVAPORATORTYPE": "IfcEvaporatorType",
  "IFCEVENT": "IfcEvent",
  "IFCEVENTTIME": "IfcEventTime",
  "IFCEVENTTYPE": "IfcEventType",
  "IFCEXTENDEDPROPERTIES": "IfcExtendedProperties",
  "IFCEXTERNALINFORMATION": "IfcExternalInformation",
  "IFCEXTERNALREFERENCE": "IfcExternalReference",
  "IFCEXTERNALREFERENCERELATIONSHIP": "IfcExternalReferenceRelationship",
  "IFCEXTERNALSPATIALELEMENT": "IfcExternalSpatialElement",
  "IFCEXTERNALSPATIALSTRUCTUREELEMENT": "IfcExternalSpatialStructureElement",
  "IFCEXTERNALLYDEFINEDHATCHSTYLE": "IfcExternallyDefinedHatchStyle",
  "IFCEXTERNALLYDEFINEDSURFACESTYLE": "IfcExternallyDefinedSurfaceStyle",
  "IFCEXTERNALLYDEFINEDTEXTFONT": "IfcExternallyDefinedTextFont",
  "IFCEXTRUDEDAREASOLID": "IfcExtrudedAreaSolid",
  "IFCEXTRUDEDAREASOLIDTAPERED": "IfcExtrudedAreaSolidTapered",
  "IFCFACE": "IfcFace",
  "IFCFACEBASEDSURFACEMODEL": "IfcFaceBasedSurfaceModel",
  "IFCFACEBOUND": "IfcFaceBound",
  "IFCFACEOUTERBOUND": "IfcFaceOuterBound",
  "IFCFACESURFACE": "IfcFaceSurface",
  "IFCFACETEDBREP": "IfcFacetedBrep",
  "IFCFACETEDBREPWITHVOIDS": "IfcFacetedBrepWithVoids",
  "IFCFACILITY": "IfcFacility",
  "IFCFACILITYPART": "IfcFacilityPart",
  "IFCFACILITYPARTCOMMON": "IfcFacilityPartCommon",
  "IFCFAILURECONNECTIONCONDITION": "IfcFailureConnectionCondition",
  "IFCFAN": "IfcFan",
  "IFCFANTYPE": "IfcFanType",
  "IFCFASTENER": "IfcFastener",
  "IFCFASTENERTYPE": "IfcFastenerType",
  "IFCFEATUREELEMENT": "IfcFeatureElement",
  "IFCFEATUREELEMENTADDITION": "IfcFeatureElementAddition",
  "IFCFEATUREELEMENTSUBTRACTION": "IfcFeatureElementSubtraction",
  "IFCFILLAREASTYLE": "IfcFillAreaStyle",
  "IFCFILLAREASTYLEHATCHING": "IfcFillAreaStyleHatching",
  "IFCFILLAREASTYLETILES": "IfcFillAreaStyleTiles",
  "IFCFILTER": "IfcFilter",
  "IFCFILTERTYPE": "IfcFilterType",
  "IFCFIRESUPPRESSIONTERMINAL": "IfcFireSuppressionTerminal",
  "IFCFIRESUPPRESSIONTERMINALTYPE": "IfcFireSuppressionTerminalType",
  "IFCFIXEDREFERENCESWEPTAREASOLID": "IfcFixedReferenceSweptAreaSolid",
  "IFCFLOWCONTROLLER": "IfcFlowController",
  "IFCFLOWCONTROLLERTYPE": "IfcFlowControllerType",
  "IFCFLOWFITTING": "IfcFlowFitting",
  "IFCFLOWFITTINGTYPE": "IfcFlowFittingType",
  "IFCFLOWINSTRUMENT": "IfcFlowInstrument",
  "IFCFLOWINSTRUMENTTYPE": "IfcFlowInstrumentType",
  "IFCFLOWMETER": "IfcFlowMeter",
  "IFCFLOWMETERTYPE": "IfcFlowMeterType",
  "IFCFLOWMOVINGDEVICE": "IfcFlowMovingDevice",
  "IFCFLOWMOVINGDEVICETYPE": "IfcFlowMovingDeviceType",
  "IFCFLOWSEGMENT": "IfcFlowSegment",
  "IFCFLOWSEGMENTTYPE": "IfcFlowSegmentType",
  "IFCFLOWSTORAGEDEVICE": "IfcFlowStorageDevice",
  "IFCFLOWSTORAGEDEVICETYPE": "IfcFlowStorageDeviceType",
  "IFCFLOWTERMINAL": "IfcFlowTerminal",
  "IFCFLOWTERMINALTYPE": "IfcFlowTerminalType",
  "IFCFLOWTREATMENTDEVICE": "IfcFlowTreatmentDevice",
  "IFCFLOWTREATMENTDEVICETYPE": "IfcFlowTreatmentDeviceType",
  "IFCFOOTING": "IfcFooting",
  "IFCFOOTINGTYPE": "IfcFootingType",
  "IFCFURNISHINGELEMENT": "IfcFurnishingElement",
  "IFCFURNISHINGELEMENTTYPE": "IfcFurnishingElementType",
  "IFCFURNITURE": "IfcFurniture",
  "IFCFURNITURETYPE": "IfcFurnitureType",
  "IFCGEOGRAPHICCRS": "IfcGeographicCRS",
  "IFCGEOGRAPHICELEMENT": "IfcGeographicElement",
  "IFCGEOGRAPHICELEMENTTYPE": "IfcGeographicElementType",
  "IFCGEOMETRICCURVESET": "IfcGeometricCurveSet",
  "IFCGEOMETRICREPRESENTATIONCONTEXT": "IfcGeometricRepresentationContext",
  "IFCGEOMETRICREPRESENTATIONITEM": "IfcGeometricRepresentationItem",
  "IFCGEOMETRICREPRESENTATIONSUBCONTEXT": "IfcGeometricRepresentationSubContext",
  "IFCGEOMETRICSET": "IfcGeometricSet",
  "IFCGEOMODEL": "IfcGeomodel",
  "IFCGEOSLICE": "IfcGeoslice",
  "IFCGEOTECHNICALASSEMBLY": "IfcGeotechnicalAssembly",
  "IFCGEOTECHNICALELEMENT": "IfcGeotechnicalElement",
  "IFCGEOTECHNICALSTRATUM": "IfcGeotechnicalStratum",
  "IFCGRADIENTCURVE": "IfcGradientCurve",
  "IFCGRID": "IfcGrid",
  "IFCGRIDAXIS": "IfcGridAxis",
  "IFCGRIDPLACEMENT": "IfcGridPlacement",
  "IFCGROUP": "IfcGroup",
  "IFCHALFSPACESOLID": "IfcHalfSpaceSolid",
  "IFCHEATEXCHANGER": "IfcHeatExchanger",
  "IFCHEATEXCHANGERTYPE": "IfcHeatExchangerType",
  "IFCHUMIDIFIER": "IfcHumidifier",
  "IFCHUMIDIFIERTYPE": "IfcHumidifierType",
  "IFCISHAPEPROFILEDEF": "IfcIShapeProfileDef",
  "IFCIMAGETEXTURE": "IfcImageTexture",
  "IFCIMPACTPROTECTIONDEVICE": "IfcImpactProtectionDevice",
  "IFCIMPACTPROTECTIONDEVICETYPE": "IfcImpactProtectionDeviceType",
  "IFCINDEXEDCOLOURMAP": "IfcIndexedColourMap",
  "IFCINDEXEDPOLYCURVE": "IfcIndexedPolyCurve",
  "IFCINDEXEDPOLYGONALFACE": "IfcIndexedPolygonalFace",
  "IFCINDEXEDPOLYGONALFACEWITHVOIDS": "IfcIndexedPolygonalFaceWithVoids",
  "IFCINDEXEDPOLYGONALTEXTUREMAP": "IfcIndexedPolygonalTextureMap",
  "IFCINDEXEDTEXTUREMAP": "IfcIndexedTextureMap",
  "IFCINDEXEDTRIANGLETEXTUREMAP": "IfcIndexedTriangleTextureMap",
  "IFCINTERCEPTOR": "IfcInterceptor",
  "IFCINTERCEPTORTYPE": "IfcInterceptorType",
  "IFCINTERSECTIONCURVE": "IfcIntersectionCurve",
  "IFCINVENTORY": "IfcInventory",
  "IFCIRREGULARTIMESERIES": "IfcIrregularTimeSeries",
  "IFCIRREGULARTIMESERIESVALUE": "IfcIrregularTimeSeriesValue",
  "IFCJUNCTIONBOX": "IfcJunctionBox",
  "IFCJUNCTIONBOXTYPE": "IfcJunctionBoxType",
  "IFCKERB": "IfcKerb",
  "IFCKERBTYPE": "IfcKerbType",
  "IFCLSHAPEPROFILEDEF": "IfcLShapeProfileDef",
  "IFCLABORRESOURCE": "IfcLaborResource",
  "IFCLABORRESOURCETYPE": "IfcLaborResourceType",
  "IFCLAGTIME": "IfcLagTime",
  "IFCLAMP": "IfcLamp",
  "IFCLAMPTYPE": "IfcLampType",
  "IFCLIBRARYINFORMATION": "IfcLibraryInformation",
  "IFCLIBRARYREFERENCE": "IfcLibraryReference",
  "IFCLIGHTDISTRIBUTIONDATA": "IfcLightDistributionData",
  "IFCLIGHTFIXTURE": "IfcLightFixture",
  "IFCLIGHTFIXTURETYPE": "IfcLightFixtureType",
  "IFCLIGHTINTENSITYDISTRIBUTION": "IfcLightIntensityDistribution",
  "IFCLIGHTSOURCE": "IfcLightSource",
  "IFCLIGHTSOURCEAMBIENT": "IfcLightSourceAmbient",
  "IFCLIGHTSOURCEDIRECTIONAL": "IfcLightSourceDirectional",
  "IFCLIGHTSOURCEGONIOMETRIC": "IfcLightSourceGoniometric",
  "IFCLIGHTSOURCEPOSITIONAL": "IfcLightSourcePositional",
  "IFCLIGHTSOURCESPOT": "IfcLightSourceSpot",
  "IFCLINE": "IfcLine",
  "IFCLINEARELEMENT": "IfcLinearElement",
  "IFCLINEARPLACEMENT": "IfcLinearPlacement",
  "IFCLINEARPOSITIONINGELEMENT": "IfcLinearPositioningElement",
  "IFCLIQUIDTERMINAL": "IfcLiquidTerminal",
  "IFCLIQUIDTERMINALTYPE": "IfcLiquidTerminalType",
  "IFCLOCALPLACEMENT": "IfcLocalPlacement",
  "IFCLOOP": "IfcLoop",
  "IFCMANIFOLDSOLIDBREP": "IfcManifoldSolidBrep",
  "IFCMAPCONVERSION": "IfcMapConversion",
  "IFCMAPCONVERSIONSCALED": "IfcMapConversionScaled",
  "IFCMAPPEDITEM": "IfcMappedItem",
  "IFCMARINEFACILITY": "IfcMarineFacility",
  "IFCMARINEPART": "IfcMarinePart",
  "IFCMATERIAL": "IfcMaterial",
  "IFCMATERIALCLASSIFICATIONRELATIONSHIP": "IfcMaterialClassificationRelationship",
  "IFCMATERIALCONSTITUENT": "IfcMaterialConstituent",
  "IFCMATERIALCONSTITUENTSET": "IfcMaterialConstituentSet",
  "IFCMATERIALDEFINITION": "IfcMaterialDefinition",
  "IFCMATERIALDEFINITIONREPRESENTATION": "IfcMaterialDefinitionRepresentation",
  "IFCMATERIALLAYER": "IfcMaterialLayer",
  "IFCMATERIALLAYERSET": "IfcMaterialLayerSet",
  "IFCMATERIALLAYERSETUSAGE": "IfcMaterialLayerSetUsage",
  "IFCMATERIALLAYERWITHOFFSETS": "IfcMaterialLayerWithOffsets",
  "IFCMATERIALLIST": "IfcMaterialList",
  "IFCMATERIALPROFILE": "IfcMaterialProfile",
  "IFCMATERIALPROFILESET": "IfcMaterialProfileSet",
  "IFCMATERIALPROFILESETUSAGE": "IfcMaterialProfileSetUsage",
  "IFCMATERIALPROFILESETUSAGETAPERING": "IfcMaterialProfileSetUsageTapering",
  "IFCMATERIALPROFILEWITHOFFSETS": "IfcMaterialProfileWithOffsets",
  "IFCMATERIALPROPERTIES": "IfcMaterialProperties",
  "IFCMATERIALRELATIONSHIP": "IfcMaterialRelationship",
  "IFCMATERIALUSAGEDEFINITION": "IfcMaterialUsageDefinition",
  "IFCMEASUREWITHUNIT": "IfcMeasureWithUnit",
  "IFCMECHANICALFASTENER": "IfcMechanicalFastener",
  "IFCMECHANICALFASTENERTYPE": "IfcMechanicalFastenerType",
  "IFCMEDICALDEVICE": "IfcMedicalDevice",
  "IFCMEDICALDEVICETYPE": "IfcMedicalDeviceType",
  "IFCMEMBER": "IfcMember",
  "IFCMEMBERTYPE": "IfcMemberType",
  "IFCMETRIC": "IfcMetric",
  "IFCMIRROREDPROFILEDEF": "IfcMirroredProfileDef",
  "IFCMOBILETELECOMMUNICATIONSAPPLIANCE": "IfcMobileTelecommunicationsAppliance",
  "IFCMOBILETELECOMMUNICATIONSAPPLIANCETYPE": "IfcMobileTelecommunicationsApplianceType",
  "IFCMONETARYUNIT": "IfcMonetaryUnit",
  "IFCMOORINGDEVICE": "IfcMooringDevice",
  "IFCMOORINGDEVICETYPE": "IfcMooringDeviceType",
  "IFCMOTORCONNECTION": "IfcMotorConnection",
  "IFCMOTORCONNECTIONTYPE": "IfcMotorConnectionType",
  "IFCNAMEDUNIT": "IfcNamedUnit",
  "IFCNAVIGATIONELEMENT": "IfcNavigationElement",
  "IFCNAVIGATIONELEMENTTYPE": "IfcNavigationElementType",
  "IFCOBJECT": "IfcObject",
  "IFCOBJECTDEFINITION": "IfcObjectDefinition",
  "IFCOBJECTPLACEMENT": "IfcObjectPlacement",
  "IFCOBJECTIVE": "IfcObjective",
  "IFCOCCUPANT": "IfcOccupant",
  "IFCOFFSETCURVE": "IfcOffsetCurve",
  "IFCOFFSETCURVE2D": "IfcOffsetCurve2D",
  "IFCOFFSETCURVE3D": "IfcOffsetCurve3D",
  "IFCOFFSETCURVEBYDISTANCES": "IfcOffsetCurveByDistances",
  "IFCOPENCROSSPROFILEDEF": "IfcOpenCrossProfileDef",
  "IFCOPENSHELL": "IfcOpenShell",
  "IFCOPENINGELEMENT": "IfcOpeningElement",
  "IFCORGANIZATION": "IfcOrganization",
  "IFCORGANIZATIONRELATIONSHIP": "IfcOrganizationRelationship",
  "IFCORIENTEDEDGE": "IfcOrientedEdge",
  "IFCOUTERBOUNDARYCURVE": "IfcOuterBoundaryCurve",
  "IFCOUTLET": "IfcOutlet",
  "IFCOUTLETTYPE": "IfcOutletType",
  "IFCOWNERHISTORY": "IfcOwnerHistory",
  "IFCPARAMETERIZEDPROFILEDEF": "IfcParameterizedProfileDef",
  "IFCPATH": "IfcPath",
  "IFCPAVEMENT": "IfcPavement",
  "IFCPAVEMENTTYPE": "IfcPavementType",
  "IFCPCURVE": "IfcPcurve",
  "IFCPERFORMANCEHISTORY": "IfcPerformanceHistory",
  "IFCPERMEABLECOVERINGPROPERTIES": "IfcPermeableCoveringProperties",
  "IFCPERMIT": "IfcPermit",
  "IFCPERSON": "IfcPerson",
  "IFCPERSONANDORGANIZATION": "IfcPersonAndOrganization",
  "IFCPHYSICALCOMPLEXQUANTITY": "IfcPhysicalComplexQuantity",
  "IFCPHYSICALQUANTITY": "IfcPhysicalQuantity",
  "IFCPHYSICALSIMPLEQUANTITY": "IfcPhysicalSimpleQuantity",
  "IFCPILE": "IfcPile",
  "IFCPILETYPE": "IfcPileType",
  "IFCPIPEFITTING": "IfcPipeFitting",
  "IFCPIPEFITTINGTYPE": "IfcPipeFittingType",
  "IFCPIPESEGMENT": "IfcPipeSegment",
  "IFCPIPESEGMENTTYPE": "IfcPipeSegmentType",
  "IFCPIXELTEXTURE": "IfcPixelTexture",
  "IFCPLACEMENT": "IfcPlacement",
  "IFCPLANARBOX": "IfcPlanarBox",
  "IFCPLANAREXTENT": "IfcPlanarExtent",
  "IFCPLANE": "IfcPlane",
  "IFCPLATE": "IfcPlate",
  "IFCPLATETYPE": "IfcPlateType",
  "IFCPOINT": "IfcPoint",
  "IFCPOINTBYDISTANCEEXPRESSION": "IfcPointByDistanceExpression",
  "IFCPOINTONCURVE": "IfcPointOnCurve",
  "IFCPOINTONSURFACE": "IfcPointOnSurface",
  "IFCPOLYLOOP": "IfcPolyLoop",
  "IFCPOLYGONALBOUNDEDHALFSPACE": "IfcPolygonalBoundedHalfSpace",
  "IFCPOLYGONALFACESET": "IfcPolygonalFaceSet",
  "IFCPOLYLINE": "IfcPolyline",
  "IFCPOLYNOMIALCURVE": "IfcPolynomialCurve",
  "IFCPORT": "IfcPort",
  "IFCPOSITIONINGELEMENT": "IfcPositioningElement",
  "IFCPOSTALADDRESS": "IfcPostalAddress",
  "IFCPREDEFINEDCOLOUR": "IfcPreDefinedColour",
  "IFCPREDEFINEDCURVEFONT": "IfcPreDefinedCurveFont",
  "IFCPREDEFINEDITEM": "IfcPreDefinedItem",
  "IFCPREDEFINEDPROPERTIES": "IfcPreDefinedProperties",
  "IFCPREDEFINEDPROPERTYSET": "IfcPreDefinedPropertySet",
  "IFCPREDEFINEDTEXTFONT": "IfcPreDefinedTextFont",
  "IFCPRESENTATIONITEM": "IfcPresentationItem",
  "IFCPRESENTATIONLAYERASSIGNMENT": "IfcPresentationLayerAssignment",
  "IFCPRESENTATIONLAYERWITHSTYLE": "IfcPresentationLayerWithStyle",
  "IFCPRESENTATIONSTYLE": "IfcPresentationStyle",
  "IFCPROCEDURE": "IfcProcedure",
  "IFCPROCEDURETYPE": "IfcProcedureType",
  "IFCPROCESS": "IfcProcess",
  "IFCPRODUCT": "IfcProduct",
  "IFCPRODUCTDEFINITIONSHAPE": "IfcProductDefinitionShape",
  "IFCPRODUCTREPRESENTATION": "IfcProductRepresentation",
  "IFCPROFILEDEF": "IfcProfileDef",
  "IFCPROFILEPROPERTIES": "IfcProfileProperties",
  "IFCPROJECT": "IfcProject",
  "IFCPROJECTLIBRARY": "IfcProjectLibrary",
  "IFCPROJECTORDER": "IfcProjectOrder",
  "IFCPROJECTEDCRS": "IfcProjectedCRS",
  "IFCPROJECTIONELEMENT": "IfcProjectionElement",
  "IFCPROPERTY": "IfcProperty",
  "IFCPROPERTYABSTRACTION": "IfcPropertyAbstraction",
  "IFCPROPERTYBOUNDEDVALUE": "IfcPropertyBoundedValue",
  "IFCPROPERTYDEFINITION": "IfcPropertyDefinition",
  "IFCPROPERTYDEPENDENCYRELATIONSHIP": "IfcPropertyDependencyRelationship",
  "IFCPROPERTYENUMERATEDVALUE": "IfcPropertyEnumeratedValue",
  "IFCPROPERTYENUMERATION": "IfcPropertyEnumeration",
  "IFCPROPERTYLISTVALUE": "IfcPropertyListValue",
  "IFCPROPERTYREFERENCEVALUE": "IfcPropertyReferenceValue",
  "IFCPROPERTYSET": "IfcPropertySet",
  "IFCPROPERTYSETDEFINITION": "IfcPropertySetDefinition",
  "IFCPROPERTYSETTEMPLATE": "IfcPropertySetTemplate",
  "IFCPROPERTYSINGLEVALUE": "IfcPropertySingleValue",
  "IFCPROPERTYTABLEVALUE": "IfcPropertyTableValue",
  "IFCPROPERTYTEMPLATE": "IfcPropertyTemplate",
  "IFCPROPERTYTEMPLATEDEFINITION": "IfcPropertyTemplateDefinition",
  "IFCPROTECTIVEDEVICE": "IfcProtectiveDevice",
  "IFCPROTECTIVEDEVICETRIPPINGUNIT": "IfcProtectiveDeviceTrippingUnit",
  "IFCPROTECTIVEDEVICETRIPPINGUNITTYPE": "IfcProtectiveDeviceTrippingUnitType",
  "IFCPROTECTIVEDEVICETYPE": "IfcProtectiveDeviceType",
  "IFCPUMP": "IfcPump",
  "IFCPUMPTYPE": "IfcPumpType",
  "IFCQUANTITYAREA": "IfcQuantityArea",
  "IFCQUANTITYCOUNT": "IfcQuantityCount",
  "IFCQUANTITYLENGTH": "IfcQuantityLength",
  "IFCQUANTITYNUMBER": "IfcQuantityNumber",
  "IFCQUANTITYSET": "IfcQuantitySet",
  "IFCQUANTITYTIME": "IfcQuantityTime",
  "IFCQUANTITYVOLUME": "IfcQuantityVolume",
  "IFCQUANTITYWEIGHT": "IfcQuantityWeight",
  "IFCRAIL": "IfcRail",
  "IFCRAILTYPE": "IfcRailType",
  "IFCRAILING": "IfcRailing",
  "IFCRAILINGTYPE": "IfcRailingType",
  "IFCRAILWAY": "IfcRailway",
  "IFCRAILWAYPART": "IfcRailwayPart",
  "IFCRAMP": "IfcRamp",
  "IFCRAMPFLIGHT": "IfcRampFlight",
  "IFCRAMPFLIGHTTYPE": "IfcRampFlightType",
  "IFCRAMPTYPE": "IfcRampType",
  "IFCRATIONALBSPLINECURVEWITHKNOTS": "IfcRationalBSplineCurveWithKnots",
  "IFCRATIONALBSPLINESURFACEWITHKNOTS": "IfcRationalBSplineSurfaceWithKnots",
  "IFCRECTANGLEHOLLOWPROFILEDEF": "IfcRectangleHollowProfileDef",
  "IFCRECTANGLEPROFILEDEF": "IfcRectangleProfileDef",
  "IFCRECTANGULARPYRAMID": "IfcRectangularPyramid",
  "IFCRECTANGULARTRIMMEDSURFACE": "IfcRectangularTrimmedSurface",
  "IFCRECURRENCEPATTERN": "IfcRecurrencePattern",
  "IFCREFERENCE": "IfcReference",
  "IFCREFERENT": "IfcReferent",
  "IFCREGULARTIMESERIES": "IfcRegularTimeSeries",
  "IFCREINFORCEDSOIL": "IfcReinforcedSoil",
  "IFCREINFORCEMENTBARPROPERTIES": "IfcReinforcementBarProperties",
  "IFCREINFORCEMENTDEFINITIONPROPERTIES": "IfcReinforcementDefinitionProperties",
  "IFCREINFORCINGBAR": "IfcReinforcingBar",
  "IFCREINFORCINGBARTYPE": "IfcReinforcingBarType",
  "IFCREINFORCINGELEMENT": "IfcReinforcingElement",
  "IFCREINFORCINGELEMENTTYPE": "IfcReinforcingElementType",
  "IFCREINFORCINGMESH": "IfcReinforcingMesh",
  "IFCREINFORCINGMESHTYPE": "IfcReinforcingMeshType",
  "IFCRELADHERESTOELEMENT": "IfcRelAdheresToElement",
  "IFCRELAGGREGATES": "IfcRelAggregates",
  "IFCRELASSIGNS": "IfcRelAssigns",
  "IFCRELASSIGNSTOACTOR": "IfcRelAssignsToActor",
  "IFCRELASSIGNSTOCONTROL": "IfcRelAssignsToControl",
  "IFCRELASSIGNSTOGROUP": "IfcRelAssignsToGroup",
  "IFCRELASSIGNSTOGROUPBYFACTOR": "IfcRelAssignsToGroupByFactor",
  "IFCRELASSIGNSTOPROCESS": "IfcRelAssignsToProcess",
  "IFCRELASSIGNSTOPRODUCT": "IfcRelAssignsToProduct",
  "IFCRELASSIGNSTORESOURCE": "IfcRelAssignsToResource",
  "IFCRELASSOCIATES": "IfcRelAssociates",
  "IFCRELASSOCIATESAPPROVAL": "IfcRelAssociatesApproval",
  "IFCRELASSOCIATESCLASSIFICATION": "IfcRelAssociatesClassification",
  "IFCRELASSOCIATESCONSTRAINT": "IfcRelAssociatesConstraint",
  "IFCRELASSOCIATESDOCUMENT": "IfcRelAssociatesDocument",
  "IFCRELASSOCIATESLIBRARY": "IfcRelAssociatesLibrary",
  "IFCRELASSOCIATESMATERIAL": "IfcRelAssociatesMaterial",
  "IFCRELASSOCIATESPROFILEDEF": "IfcRelAssociatesProfileDef",
  "IFCRELCONNECTS": "IfcRelConnects",
  "IFCRELCONNECTSELEMENTS": "IfcRelConnectsElements",
  "IFCRELCONNECTSPATHELEMENTS": "IfcRelConnectsPathElements",
  "IFCRELCONNECTSPORTTOELEMENT": "IfcRelConnectsPortToElement",
  "IFCRELCONNECTSPORTS": "IfcRelConnectsPorts",
  "IFCRELCONNECTSSTRUCTURALACTIVITY": "IfcRelConnectsStructuralActivity",
  "IFCRELCONNECTSSTRUCTURALMEMBER": "IfcRelConnectsStructuralMember",
  "IFCRELCONNECTSWITHECCENTRICITY": "IfcRelConnectsWithEccentricity",
  "IFCRELCONNECTSWITHREALIZINGELEMENTS": "IfcRelConnectsWithRealizingElements",
  "IFCRELCONTAINEDINSPATIALSTRUCTURE": "IfcRelContainedInSpatialStructure",
  "IFCRELCOVERSBLDGELEMENTS": "IfcRelCoversBldgElements",
  "IFCRELCOVERSSPACES": "IfcRelCoversSpaces",
  "IFCRELDECLARES": "IfcRelDeclares",
  "IFCRELDECOMPOSES": "IfcRelDecomposes",
  "IFCRELDEFINES": "IfcRelDefines",
  "IFCRELDEFINESBYOBJECT": "IfcRelDefinesByObject",
  "IFCRELDEFINESBYPROPERTIES": "IfcRelDefinesByProperties",
  "IFCRELDEFINESBYTEMPLATE": "IfcRelDefinesByTemplate",
  "IFCRELDEFINESBYTYPE": "IfcRelDefinesByType",
  "IFCRELFILLSELEMENT": "IfcRelFillsElement",
  "IFCRELFLOWCONTROLELEMENTS": "IfcRelFlowControlElements",
  "IFCRELINTERFERESELEMENTS": "IfcRelInterferesElements",
  "IFCRELNESTS": "IfcRelNests",
  "IFCRELPOSITIONS": "IfcRelPositions",
  "IFCRELPROJECTSELEMENT": "IfcRelProjectsElement",
  "IFCRELREFERENCEDINSPATIALSTRUCTURE": "IfcRelReferencedInSpatialStructure",
  "IFCRELSEQUENCE": "IfcRelSequence",
  "IFCRELSERVICESBUILDINGS": "IfcRelServicesBuildings",
  "IFCRELSPACEBOUNDARY": "IfcRelSpaceBoundary",
  "IFCRELSPACEBOUNDARY1STLEVEL": "IfcRelSpaceBoundary1stLevel",
  "IFCRELSPACEBOUNDARY2NDLEVEL": "IfcRelSpaceBoundary2ndLevel",
  "IFCRELVOIDSELEMENT": "IfcRelVoidsElement",
  "IFCRELATIONSHIP": "IfcRelationship",
  "IFCREPARAMETRISEDCOMPOSITECURVESEGMENT": "IfcReparametrisedCompositeCurveSegment",
  "IFCREPRESENTATION": "IfcRepresentation",
  "IFCREPRESENTATIONCONTEXT": "IfcRepresentationContext",
  "IFCREPRESENTATIONITEM": "IfcRepresentationItem",
  "IFCREPRESENTATIONMAP": "IfcRepresentationMap",
  "IFCRESOURCE": "IfcResource",
  "IFCRESOURCEAPPROVALRELATIONSHIP": "IfcResourceApprovalRelationship",
  "IFCRESOURCECONSTRAINTRELATIONSHIP": "IfcResourceConstraintRelationship",
  "IFCRESOURCELEVELRELATIONSHIP": "IfcResourceLevelRelationship",
  "IFCRESOURCETIME": "IfcResourceTime",
  "IFCREVOLVEDAREASOLID": "IfcRevolvedAreaSolid",
  "IFCREVOLVEDAREASOLIDTAPERED": "IfcRevolvedAreaSolidTapered",
  "IFCRIGHTCIRCULARCONE": "IfcRightCircularCone",
  "IFCRIGHTCIRCULARCYLINDER": "IfcRightCircularCylinder",
  "IFCRIGIDOPERATION": "IfcRigidOperation",
  "IFCROAD": "IfcRoad",
  "IFCROADPART": "IfcRoadPart",
  "IFCROOF": "IfcRoof",
  "IFCROOFTYPE": "IfcRoofType",
  "IFCROOT": "IfcRoot",
  "IFCROUNDEDRECTANGLEPROFILEDEF": "IfcRoundedRectangleProfileDef",
  "IFCSIUNIT": "IfcSIUnit",
  "IFCSANITARYTERMINAL": "IfcSanitaryTerminal",
  "IFCSANITARYTERMINALTYPE": "IfcSanitaryTerminalType",
  "IFCSCHEDULINGTIME": "IfcSchedulingTime",
  "IFCSEAMCURVE": "IfcSeamCurve",
  "IFCSECONDORDERPOLYNOMIALSPIRAL": "IfcSecondOrderPolynomialSpiral",
  "IFCSECTIONPROPERTIES": "IfcSectionProperties",
  "IFCSECTIONREINFORCEMENTPROPERTIES": "IfcSectionReinforcementProperties",
  "IFCSECTIONEDSOLID": "IfcSectionedSolid",
  "IFCSECTIONEDSOLIDHORIZONTAL": "IfcSectionedSolidHorizontal",
  "IFCSECTIONEDSPINE": "IfcSectionedSpine",
  "IFCSECTIONEDSURFACE": "IfcSectionedSurface",
  "IFCSEGMENT": "IfcSegment",
  "IFCSEGMENTEDREFERENCECURVE": "IfcSegmentedReferenceCurve",
  "IFCSENSOR": "IfcSensor",
  "IFCSENSORTYPE": "IfcSensorType",
  "IFCSEVENTHORDERPOLYNOMIALSPIRAL": "IfcSeventhOrderPolynomialSpiral",
  "IFCSHADINGDEVICE": "IfcShadingDevice",
  "IFCSHADINGDEVICETYPE": "IfcShadingDeviceType",
  "IFCSHAPEASPECT": "IfcShapeAspect",
  "IFCSHAPEMODEL": "IfcShapeModel",
  "IFCSHAPEREPRESENTATION": "IfcShapeRepresentation",
  "IFCSHELLBASEDSURFACEMODEL": "IfcShellBasedSurfaceModel",
  "IFCSIGN": "IfcSign",
  "IFCSIGNTYPE": "IfcSignType",
  "IFCSIGNAL": "IfcSignal",
  "IFCSIGNALTYPE": "IfcSignalType",
  "IFCSIMPLEPROPERTY": "IfcSimpleProperty",
  "IFCSIMPLEPROPERTYTEMPLATE": "IfcSimplePropertyTemplate",
  "IFCSINESPIRAL": "IfcSineSpiral",
  "IFCSITE": "IfcSite",
  "IFCSLAB": "IfcSlab",
  "IFCSLABTYPE": "IfcSlabType",
  "IFCSLIPPAGECONNECTIONCONDITION": "IfcSlippageConnectionCondition",
  "IFCSOLARDEVICE": "IfcSolarDevice",
  "IFCSOLARDEVICETYPE": "IfcSolarDeviceType",
  "IFCSOLIDMODEL": "IfcSolidModel",
  "IFCSPACE": "IfcSpace",
  "IFCSPACEHEATER": "IfcSpaceHeater",
  "IFCSPACEHEATERTYPE": "IfcSpaceHeaterType",
  "IFCSPACETYPE": "IfcSpaceType",
  "IFCSPATIALELEMENT": "IfcSpatialElement",
  "IFCSPATIALELEMENTTYPE": "IfcSpatialElementType",
  "IFCSPATIALSTRUCTUREELEMENT": "IfcSpatialStructureElement",
  "IFCSPATIALSTRUCTUREELEMENTTYPE": "IfcSpatialStructureElementType",
  "IFCSPATIALZONE": "IfcSpatialZone",
  "IFCSPATIALZONETYPE": "IfcSpatialZoneType",
  "IFCSPHERE": "IfcSphere",
  "IFCSPHERICALSURFACE": "IfcSphericalSurface",
  "IFCSPIRAL": "IfcSpiral",
  "IFCSTACKTERMINAL": "IfcStackTerminal",
  "IFCSTACKTERMINALTYPE": "IfcStackTerminalType",
  "IFCSTAIR": "IfcStair",
  "IFCSTAIRFLIGHT": "IfcStairFlight",
  "IFCSTAIRFLIGHTTYPE": "IfcStairFlightType",
  "IFCSTAIRTYPE": "IfcStairType",
  "IFCSTRUCTURALACTION": "IfcStructuralAction",
  "IFCSTRUCTURALACTIVITY": "IfcStructuralActivity",
  "IFCSTRUCTURALANALYSISMODEL": "IfcStructuralAnalysisModel",
  "IFCSTRUCTURALCONNECTION": "IfcStructuralConnection",
  "IFCSTRUCTURALCONNECTIONCONDITION": "IfcStructuralConnectionCondition",
  "IFCSTRUCTURALCURVEACTION": "IfcStructuralCurveAction",
  "IFCSTRUCTURALCURVECONNECTION": "IfcStructuralCurveConnection",
  "IFCSTRUCTURALCURVEMEMBER": "IfcStructuralCurveMember",
  "IFCSTRUCTURALCURVEMEMBERVARYING": "IfcStructuralCurveMemberVarying",
  "IFCSTRUCTURALCURVEREACTION": "IfcStructuralCurveReaction",
  "IFCSTRUCTURALITEM": "IfcStructuralItem",
  "IFCSTRUCTURALLINEARACTION": "IfcStructuralLinearAction",
  "IFCSTRUCTURALLOAD": "IfcStructuralLoad",
  "IFCSTRUCTURALLOADCASE": "IfcStructuralLoadCase",
  "IFCSTRUCTURALLOADCONFIGURATION": "IfcStructuralLoadConfiguration",
  "IFCSTRUCTURALLOADGROUP": "IfcStructuralLoadGroup",
  "IFCSTRUCTURALLOADLINEARFORCE": "IfcStructuralLoadLinearForce",
  "IFCSTRUCTURALLOADORRESULT": "IfcStructuralLoadOrResult",
  "IFCSTRUCTURALLOADPLANARFORCE": "IfcStructuralLoadPlanarForce",
  "IFCSTRUCTURALLOADSINGLEDISPLACEMENT": "IfcStructuralLoadSingleDisplacement",
  "IFCSTRUCTURALLOADSINGLEDISPLACEMENTDISTORTION": "IfcStructuralLoadSingleDisplacementDistortion",
  "IFCSTRUCTURALLOADSINGLEFORCE": "IfcStructuralLoadSingleForce",
  "IFCSTRUCTURALLOADSINGLEFORCEWARPING": "IfcStructuralLoadSingleForceWarping",
  "IFCSTRUCTURALLOADSTATIC": "IfcStructuralLoadStatic",
  "IFCSTRUCTURALLOADTEMPERATURE": "IfcStructuralLoadTemperature",
  "IFCSTRUCTURALMEMBER": "IfcStructuralMember",
  "IFCSTRUCTURALPLANARACTION": "IfcStructuralPlanarAction",
  "IFCSTRUCTURALPOINTACTION": "IfcStructuralPointAction",
  "IFCSTRUCTURALPOINTCONNECTION": "IfcStructuralPointConnection",
  "IFCSTRUCTURALPOINTREACTION": "IfcStructuralPointReaction",
  "IFCSTRUCTURALREACTION": "IfcStructuralReaction",
  "IFCSTRUCTURALRESULTGROUP": "IfcStructuralResultGroup",
  "IFCSTRUCTURALSURFACEACTION": "IfcStructuralSurfaceAction",
  "IFCSTRUCTURALSURFACECONNECTION": "IfcStructuralSurfaceConnection",
  "IFCSTRUCTURALSURFACEMEMBER": "IfcStructuralSurfaceMember",
  "IFCSTRUCTURALSURFACEMEMBERVARYING": "IfcStructuralSurfaceMemberVarying",
  "IFCSTRUCTURALSURFACEREACTION": "IfcStructuralSurfaceReaction",
  "IFCSTYLEMODEL": "IfcStyleModel",
  "IFCSTYLEDITEM": "IfcStyledItem",
  "IFCSTYLEDREPRESENTATION": "IfcStyledRepresentation",
  "IFCSUBCONTRACTRESOURCE": "IfcSubContractResource",
  "IFCSUBCONTRACTRESOURCETYPE": "IfcSubContractResourceType",
  "IFCSUBEDGE": "IfcSubedge",
  "IFCSURFACE": "IfcSurface",
  "IFCSURFACECURVE": "IfcSurfaceCurve",
  "IFCSURFACECURVESWEPTAREASOLID": "IfcSurfaceCurveSweptAreaSolid",
  "IFCSURFACEFEATURE": "IfcSurfaceFeature",
  "IFCSURFACEOFLINEAREXTRUSION": "IfcSurfaceOfLinearExtrusion",
  "IFCSURFACEOFREVOLUTION": "IfcSurfaceOfRevolution",
  "IFCSURFACEREINFORCEMENTAREA": "IfcSurfaceReinforcementArea",
  "IFCSURFACESTYLE": "IfcSurfaceStyle",
  "IFCSURFACESTYLELIGHTING": "IfcSurfaceStyleLighting",
  "IFCSURFACESTYLEREFRACTION": "IfcSurfaceStyleRefraction",
  "IFCSURFACESTYLERENDERING": "IfcSurfaceStyleRendering",
  "IFCSURFACESTYLESHADING": "IfcSurfaceStyleShading",
  "IFCSURFACESTYLEWITHTEXTURES": "IfcSurfaceStyleWithTextures",
  "IFCSURFACETEXTURE": "IfcSurfaceTexture",
  "IFCSWEPTAREASOLID": "IfcSweptAreaSolid",
  "IFCSWEPTDISKSOLID": "IfcSweptDiskSolid",
  "IFCSWEPTDISKSOLIDPOLYGONAL": "IfcSweptDiskSolidPolygonal",
  "IFCSWEPTSURFACE": "IfcSweptSurface",
  "IFCSWITCHINGDEVICE": "IfcSwitchingDevice",
  "IFCSWITCHINGDEVICETYPE": "IfcSwitchingDeviceType",
  "IFCSYSTEM": "IfcSystem",
  "IFCSYSTEMFURNITUREELEMENT": "IfcSystemFurnitureElement",
  "IFCSYSTEMFURNITUREELEMENTTYPE": "IfcSystemFurnitureElementType",
  "IFCTSHAPEPROFILEDEF": "IfcTShapeProfileDef",
  "IFCTABLE": "IfcTable",
  "IFCTABLECOLUMN": "IfcTableColumn",
  "IFCTABLEROW": "IfcTableRow",
  "IFCTANK": "IfcTank",
  "IFCTANKTYPE": "IfcTankType",
  "IFCTASK": "IfcTask",
  "IFCTASKTIME": "IfcTaskTime",
  "IFCTASKTIMERECURRING": "IfcTaskTimeRecurring",
  "IFCTASKTYPE": "IfcTaskType",
  "IFCTELECOMADDRESS": "IfcTelecomAddress",
  "IFCTENDON": "IfcTendon",
  "IFCTENDONANCHOR": "IfcTendonAnchor",
  "IFCTENDONANCHORTYPE": "IfcTendonAnchorType",
  "IFCTENDONCONDUIT": "IfcTendonConduit",
  "IFCTENDONCONDUITTYPE": "IfcTendonConduitType",
  "IFCTENDONTYPE": "IfcTendonType",
  "IFCTESSELLATEDFACESET": "IfcTessellatedFaceSet",
  "IFCTESSELLATEDITEM": "IfcTessellatedItem",
  "IFCTEXTLITERAL": "IfcTextLiteral",
  "IFCTEXTLITERALWITHEXTENT": "IfcTextLiteralWithExtent",
  "IFCTEXTSTYLE": "IfcTextStyle",
  "IFCTEXTSTYLEFONTMODEL": "IfcTextStyleFontModel",
  "IFCTEXTSTYLEFORDEFINEDFONT": "IfcTextStyleForDefinedFont",
  "IFCTEXTSTYLETEXTMODEL": "IfcTextStyleTextModel",
  "IFCTEXTURECOORDINATE": "IfcTextureCoordinate",
  "IFCTEXTURECOORDINATEGENERATOR": "IfcTextureCoordinateGenerator",
  "IFCTEXTURECOORDINATEINDICES": "IfcTextureCoordinateIndices",
  "IFCTEXTURECOORDINATEINDICESWITHVOIDS": "IfcTextureCoordinateIndicesWithVoids",
  "IFCTEXTUREMAP": "IfcTextureMap",
  "IFCTEXTUREVERTEX": "IfcTextureVertex",
  "IFCTEXTUREVERTEXLIST": "IfcTextureVertexList",
  "IFCTHIRDORDERPOLYNOMIALSPIRAL": "IfcThirdOrderPolynomialSpiral",
  "IFCTIMEPERIOD": "IfcTimePeriod",
  "IFCTIMESERIES": "IfcTimeSeries",
  "IFCTIMESERIESVALUE": "IfcTimeSeriesValue",
  "IFCTOPOLOGICALREPRESENTATIONITEM": "IfcTopologicalRepresentationItem",
  "IFCTOPOLOGYREPRESENTATION": "IfcTopologyRepresentation",
  "IFCTOROIDALSURFACE": "IfcToroidalSurface",
  "IFCTRACKELEMENT": "IfcTrackElement",
  "IFCTRACKELEMENTTYPE": "IfcTrackElementType",
  "IFCTRANSFORMER": "IfcTransformer",
  "IFCTRANSFORMERTYPE": "IfcTransformerType",
  "IFCTRANSPORTELEMENT": "IfcTransportElement",
  "IFCTRANSPORTELEMENTTYPE": "IfcTransportElementType",
  "IFCTRANSPORTATIONDEVICE": "IfcTransportationDevice",
  "IFCTRANSPORTATIONDEVICETYPE": "IfcTransportationDeviceType",
  "IFCTRAPEZIUMPROFILEDEF": "IfcTrapeziumProfileDef",
  "IFCTRIANGULATEDFACESET": "IfcTriangulatedFaceSet",
  "IFCTRIANGULATEDIRREGULARNETWORK": "IfcTriangulatedIrregularNetwork",
  "IFCTRIMMEDCURVE": "IfcTrimmedCurve",
  "IFCTUBEBUNDLE": "IfcTubeBundle",
  "IFCTUBEBUNDLETYPE": "IfcTubeBundleType",
  "IFCTYPEOBJECT": "IfcTypeObject",
  "IFCTYPEPROCESS": "IfcTypeProcess",
  "IFCTYPEPRODUCT": "IfcTypeProduct",
  "IFCTYPERESOURCE": "IfcTypeResource",
  "IFCUSHAPEPROFILEDEF": "IfcUShapeProfileDef",
  "IFCUNITASSIGNMENT": "IfcUnitAssignment",
  "IFCUNITARYCONTROLELEMENT": "IfcUnitaryControlElement",
  "IFCUNITARYCONTROLELEMENTTYPE": "IfcUnitaryControlElementType",
  "IFCUNITARYEQUIPMENT": "IfcUnitaryEquipment",
  "IFCUNITARYEQUIPMENTTYPE": "IfcUnitaryEquipmentType",
  "IFCVALVE": "IfcValve",
  "IFCVALVETYPE": "IfcValveType",
  "IFCVECTOR": "IfcVector",
  "IFCVEHICLE": "IfcVehicle",
  "IFCVEHICLETYPE": "IfcVehicleType",
  "IFCVERTEX": "IfcVertex",
  "IFCVERTEXLOOP": "IfcVertexLoop",
  "IFCVERTEXPOINT": "IfcVertexPoint",
  "IFCVIBRATIONDAMPER": "IfcVibrationDamper",
  "IFCVIBRATIONDAMPERTYPE": "IfcVibrationDamperType",
  "IFCVIBRATIONISOLATOR": "IfcVibrationIsolator",
  "IFCVIBRATIONISOLATORTYPE": "IfcVibrationIsolatorType",
  "IFCVIRTUALELEMENT": "IfcVirtualElement",
  "IFCVIRTUALGRIDINTERSECTION": "IfcVirtualGridIntersection",
  "IFCVOIDINGFEATURE": "IfcVoidingFeature",
  "IFCWALL": "IfcWall",
  "IFCWALLSTANDARDCASE": "IfcWallStandardCase",
  "IFCWALLTYPE": "IfcWallType",
  "IFCWASTETERMINAL": "IfcWasteTerminal",
  "IFCWASTETERMINALTYPE": "IfcWasteTerminalType",
  "IFCWELLKNOWNTEXT": "IfcWellKnownText",
  "IFCWINDOW": "IfcWindow",
  "IFCWINDOWLININGPROPERTIES": "IfcWindowLiningProperties",
  "IFCWINDOWPANELPROPERTIES": "IfcWindowPanelProperties",
  "IFCWINDOWTYPE": "IfcWindowType",
  "IFCWORKCALENDAR": "IfcWorkCalendar",
  "IFCWORKCONTROL": "IfcWorkControl",
  "IFCWORKPLAN": "IfcWorkPlan",
  "IFCWORKSCHEDULE": "IfcWorkSchedule",
  "IFCWORKTIME": "IfcWorkTime",
  "IFCZSHAPEPROFILEDEF": "IfcZShapeProfileDef",
  "IFCZONE": "IfcZone"
};

// viewer/node_modules/@ifc-lite/data/dist/entity-table.js
function normalizeIfcUpperCase(upper) {
  return IFC_ENTITY_NAMES[upper] ?? upper;
}
var EntityTableBuilder = class {
  count = 0;
  strings;
  expressId;
  typeEnum;
  globalId;
  name;
  description;
  objectType;
  flags;
  containedInStorey;
  definedByType;
  geometryIndex;
  /** Raw type name string index (for fallback display of unknown types) */
  rawTypeName;
  typeStarts = /* @__PURE__ */ new Map();
  typeCounts = /* @__PURE__ */ new Map();
  constructor(capacity, strings) {
    this.strings = strings;
    this.expressId = new Uint32Array(capacity);
    this.typeEnum = new Uint16Array(capacity);
    this.globalId = new Uint32Array(capacity);
    this.name = new Uint32Array(capacity);
    this.description = new Uint32Array(capacity);
    this.objectType = new Uint32Array(capacity);
    this.flags = new Uint8Array(capacity);
    this.containedInStorey = new Int32Array(capacity).fill(-1);
    this.definedByType = new Int32Array(capacity).fill(-1);
    this.geometryIndex = new Int32Array(capacity).fill(-1);
    this.rawTypeName = new Uint32Array(capacity);
  }
  add(expressId, type, globalId, name, description, objectType, hasGeometry = false, isType = false) {
    const i = this.count++;
    this.expressId[i] = expressId;
    const typeEnum = IfcTypeEnumFromString(type);
    this.typeEnum[i] = typeEnum;
    this.globalId[i] = this.strings.intern(globalId);
    this.name[i] = this.strings.intern(name);
    this.description[i] = this.strings.intern(description);
    this.objectType[i] = this.strings.intern(objectType);
    this.rawTypeName[i] = this.strings.intern(normalizeIfcUpperCase(type));
    let flags = 0;
    if (hasGeometry)
      flags |= EntityFlags.HAS_GEOMETRY;
    if (isType)
      flags |= EntityFlags.IS_TYPE;
    this.flags[i] = flags;
    if (!this.typeStarts.has(typeEnum)) {
      this.typeStarts.set(typeEnum, i);
      this.typeCounts.set(typeEnum, 0);
    }
    this.typeCounts.set(typeEnum, this.typeCounts.get(typeEnum) + 1);
  }
  build() {
    const trim = (arr) => {
      return arr.subarray(0, this.count);
    };
    const typeRanges = /* @__PURE__ */ new Map();
    for (const [type, start] of this.typeStarts) {
      const count = this.typeCounts.get(type);
      typeRanges.set(type, { start, end: start + count });
    }
    const typeIndices = /* @__PURE__ */ new Map();
    for (let i = 0; i < this.count; i++) {
      const t = trim(this.typeEnum)[i];
      let arr = typeIndices.get(t);
      if (!arr) {
        arr = [];
        typeIndices.set(t, arr);
      }
      arr.push(i);
    }
    const expressId = trim(this.expressId);
    const typeEnum = trim(this.typeEnum);
    const globalId = trim(this.globalId);
    const name = trim(this.name);
    const description = trim(this.description);
    const objectType = trim(this.objectType);
    const flags = trim(this.flags);
    const containedInStorey = trim(this.containedInStorey);
    const definedByType = trim(this.definedByType);
    const geometryIndex = trim(this.geometryIndex);
    const rawTypeName = trim(this.rawTypeName);
    const idToIndex = /* @__PURE__ */ new Map();
    for (let i = 0; i < this.count; i++) {
      idToIndex.set(expressId[i], i);
    }
    const indexOfId = (id) => idToIndex.get(id) ?? -1;
    const globalIdToExpressId = /* @__PURE__ */ new Map();
    for (let i = 0; i < this.count; i++) {
      const gidString = this.strings.get(globalId[i]);
      if (gidString) {
        globalIdToExpressId.set(gidString, expressId[i]);
      }
    }
    return {
      count: this.count,
      expressId,
      typeEnum,
      globalId,
      name,
      description,
      objectType,
      flags,
      containedInStorey,
      definedByType,
      geometryIndex,
      typeRanges,
      getGlobalId: (id) => {
        const idx = indexOfId(id);
        return idx >= 0 ? this.strings.get(globalId[idx]) : "";
      },
      getName: (id) => {
        const idx = indexOfId(id);
        return idx >= 0 ? this.strings.get(name[idx]) : "";
      },
      getDescription: (id) => {
        const idx = indexOfId(id);
        return idx >= 0 ? this.strings.get(description[idx]) : "";
      },
      getObjectType: (id) => {
        const idx = indexOfId(id);
        return idx >= 0 ? this.strings.get(objectType[idx]) : "";
      },
      getTypeName: (id) => {
        const idx = indexOfId(id);
        if (idx < 0)
          return "Unknown";
        const enumName = IfcTypeEnumToString(typeEnum[idx]);
        if (enumName !== "Unknown")
          return enumName;
        return this.strings.get(rawTypeName[idx]) || "Unknown";
      },
      hasGeometry: (id) => {
        const idx = indexOfId(id);
        return idx >= 0 ? (flags[idx] & EntityFlags.HAS_GEOMETRY) !== 0 : false;
      },
      getByType: (type) => {
        const indices = typeIndices.get(type);
        if (!indices)
          return [];
        const ids = new Array(indices.length);
        for (let i = 0; i < indices.length; i++) {
          ids[i] = expressId[indices[i]];
        }
        return ids;
      },
      getExpressIdByGlobalId: (gid) => globalIdToExpressId.get(gid) ?? -1,
      getGlobalIdMap: () => new Map(globalIdToExpressId)
      // Defensive copy
    };
  }
};

// viewer/node_modules/@ifc-lite/data/dist/property-table.js
var PropertyTableBuilder = class {
  strings;
  rows = [];
  constructor(strings) {
    this.strings = strings;
  }
  add(row) {
    this.rows.push(row);
  }
  build() {
    const count = this.rows.length;
    const entityId = new Uint32Array(count);
    const psetName = new Uint32Array(count);
    const psetGlobalId = new Uint32Array(count);
    const propName = new Uint32Array(count);
    const propType = new Uint8Array(count);
    const valueString = new Uint32Array(count);
    const valueReal = new Float64Array(count);
    const valueInt = new Int32Array(count);
    const valueBool = new Uint8Array(count).fill(255);
    const unitId = new Int32Array(count).fill(-1);
    const entityIndex = /* @__PURE__ */ new Map();
    const psetIndex = /* @__PURE__ */ new Map();
    const propIndex = /* @__PURE__ */ new Map();
    for (let i = 0; i < count; i++) {
      const row = this.rows[i];
      entityId[i] = row.entityId;
      const psetNameIdx = this.strings.intern(row.psetName);
      const psetGlobalIdIdx = this.strings.intern(row.psetGlobalId);
      const propNameIdx = this.strings.intern(row.propName);
      psetName[i] = psetNameIdx;
      psetGlobalId[i] = psetGlobalIdIdx;
      propName[i] = propNameIdx;
      propType[i] = row.propType;
      switch (row.propType) {
        case PropertyValueType.String:
        case PropertyValueType.Label:
        case PropertyValueType.Identifier:
        case PropertyValueType.Text:
        case PropertyValueType.Enum:
          valueString[i] = this.strings.intern(row.value);
          break;
        case PropertyValueType.Real:
          valueReal[i] = row.value;
          break;
        case PropertyValueType.Integer:
          valueInt[i] = row.value;
          break;
        case PropertyValueType.Boolean:
        case PropertyValueType.Logical:
          valueBool[i] = row.value === true ? 1 : row.value === false ? 0 : 255;
          break;
        case PropertyValueType.List:
          valueString[i] = this.strings.intern(JSON.stringify(row.value));
          break;
      }
      if (row.unitId !== void 0) {
        unitId[i] = row.unitId;
      }
      addToIndex(entityIndex, row.entityId, i);
      addToIndex(psetIndex, psetNameIdx, i);
      addToIndex(propIndex, propNameIdx, i);
    }
    const strings = this.strings;
    const table = {
      count,
      entityId,
      psetName,
      psetGlobalId,
      propName,
      propType,
      valueString,
      valueReal,
      valueInt,
      valueBool,
      unitId,
      entityIndex,
      psetIndex,
      propIndex,
      getForEntity: (id) => {
        const rowIndices = entityIndex.get(id) || [];
        const psets = /* @__PURE__ */ new Map();
        for (const idx of rowIndices) {
          const psetNameStr = strings.get(psetName[idx]);
          const psetGlobalIdStr = strings.get(psetGlobalId[idx]);
          if (!psets.has(psetNameStr)) {
            psets.set(psetNameStr, {
              name: psetNameStr,
              globalId: psetGlobalIdStr,
              properties: []
            });
          }
          const pset = psets.get(psetNameStr);
          const propNameStr = strings.get(propName[idx]);
          const propValue = getPropertyValue(table, idx, strings);
          pset.properties.push({
            name: propNameStr,
            type: propType[idx],
            value: propValue
          });
        }
        return Array.from(psets.values());
      },
      getPropertyValue: (id, pset, prop) => {
        const rowIndices = entityIndex.get(id) || [];
        const psetIdx = strings.indexOf(pset);
        const propIdx = strings.indexOf(prop);
        for (const idx of rowIndices) {
          if (psetName[idx] === psetIdx && propName[idx] === propIdx) {
            return getPropertyValue(table, idx, strings);
          }
        }
        return null;
      },
      findByProperty: (prop, operator, value) => {
        const propIdx = strings.indexOf(prop);
        if (propIdx < 0)
          return [];
        const rowIndices = propIndex.get(propIdx) || [];
        const results = [];
        for (const idx of rowIndices) {
          const propValue = getPropertyValue(table, idx, strings);
          if (compareValues(propValue, operator, value)) {
            results.push(entityId[idx]);
          }
        }
        return results;
      }
    };
    return table;
  }
};
function addToIndex(index, key, value) {
  let list = index.get(key);
  if (!list) {
    list = [];
    index.set(key, list);
  }
  list.push(value);
}
function getPropertyValue(table, idx, strings) {
  const type = table.propType[idx];
  switch (type) {
    case PropertyValueType.String:
    case PropertyValueType.Label:
    case PropertyValueType.Identifier:
    case PropertyValueType.Text:
    case PropertyValueType.Enum:
      return table.valueString[idx] >= 0 ? strings.get(table.valueString[idx]) : null;
    case PropertyValueType.Real:
      return table.valueReal[idx];
    case PropertyValueType.Integer:
      return table.valueInt[idx];
    case PropertyValueType.Boolean:
    case PropertyValueType.Logical:
      const boolVal = table.valueBool[idx];
      return boolVal === 255 ? null : boolVal === 1;
    case PropertyValueType.List:
      const listStr = strings.get(table.valueString[idx]);
      try {
        return JSON.parse(listStr);
      } catch {
        return [];
      }
    default:
      return null;
  }
}
function compareValues(propValue, operator, value) {
  if (propValue === null || value === null)
    return false;
  if (typeof propValue === "number" && typeof value === "number") {
    switch (operator) {
      case ">=":
        return propValue >= value;
      case ">":
        return propValue > value;
      case "<=":
        return propValue <= value;
      case "<":
        return propValue < value;
      case "=":
      case "==":
        return propValue === value;
      case "!=":
        return propValue !== value;
    }
  }
  if (typeof propValue === "string" && typeof value === "string") {
    switch (operator) {
      case "=":
      case "==":
        return propValue === value;
      case "!=":
        return propValue !== value;
      case "contains":
        return propValue.includes(value);
      case "startsWith":
        return propValue.startsWith(value);
    }
  }
  return false;
}

// viewer/node_modules/@ifc-lite/data/dist/quantity-table.js
var QuantityTableBuilder = class {
  strings;
  rows = [];
  constructor(strings) {
    this.strings = strings;
  }
  add(row) {
    this.rows.push(row);
  }
  build() {
    const count = this.rows.length;
    const entityId = new Uint32Array(count);
    const qsetName = new Uint32Array(count);
    const quantityName = new Uint32Array(count);
    const quantityType = new Uint8Array(count);
    const value = new Float64Array(count);
    const unitId = new Int32Array(count).fill(-1);
    const formula = new Uint32Array(count).fill(0);
    const entityIndex = /* @__PURE__ */ new Map();
    const qsetIndex = /* @__PURE__ */ new Map();
    const quantityIndex = /* @__PURE__ */ new Map();
    for (let i = 0; i < count; i++) {
      const row = this.rows[i];
      entityId[i] = row.entityId;
      qsetName[i] = this.strings.intern(row.qsetName);
      quantityName[i] = this.strings.intern(row.quantityName);
      quantityType[i] = row.quantityType;
      value[i] = row.value;
      if (row.unitId !== void 0) {
        unitId[i] = row.unitId;
      }
      if (row.formula) {
        formula[i] = this.strings.intern(row.formula);
      }
      addToIndex2(entityIndex, row.entityId, i);
      addToIndex2(qsetIndex, qsetName[i], i);
      addToIndex2(quantityIndex, quantityName[i], i);
    }
    return {
      count,
      entityId,
      qsetName,
      quantityName,
      quantityType,
      value,
      unitId,
      formula,
      entityIndex,
      qsetIndex,
      quantityIndex,
      getForEntity: (id) => {
        const rowIndices = entityIndex.get(id) || [];
        const qsets = /* @__PURE__ */ new Map();
        for (const idx of rowIndices) {
          const qsetNameStr = this.strings.get(qsetName[idx]);
          if (!qsets.has(qsetNameStr)) {
            qsets.set(qsetNameStr, {
              name: qsetNameStr,
              quantities: []
            });
          }
          const qset = qsets.get(qsetNameStr);
          const quantNameStr = this.strings.get(quantityName[idx]);
          qset.quantities.push({
            name: quantNameStr,
            type: quantityType[idx],
            value: value[idx],
            formula: formula[idx] > 0 ? this.strings.get(formula[idx]) : void 0
          });
        }
        return Array.from(qsets.values());
      },
      getQuantityValue: (id, qset, quant) => {
        const rowIndices = entityIndex.get(id) || [];
        const qsetIdx = this.strings.indexOf(qset);
        const quantIdx = this.strings.indexOf(quant);
        for (const idx of rowIndices) {
          if (qsetName[idx] === qsetIdx && quantityName[idx] === quantIdx) {
            return value[idx];
          }
        }
        return null;
      },
      sumByType: (quantName) => {
        const quantIdx = this.strings.indexOf(quantName);
        if (quantIdx < 0)
          return 0;
        const rowIndices = quantityIndex.get(quantIdx) || [];
        let sum = 0;
        for (const idx of rowIndices) {
          sum += value[idx];
        }
        return sum;
      }
    };
  }
};
function addToIndex2(index, key, value) {
  let list = index.get(key);
  if (!list) {
    list = [];
    index.set(key, list);
  }
  list.push(value);
}

// viewer/node_modules/@ifc-lite/data/dist/relationship-graph.js
var RelationshipGraphBuilder = class {
  _sources = [];
  _targets = [];
  _types = [];
  _relIds = [];
  addEdge(source, target, type, relId) {
    this._sources.push(source);
    this._targets.push(target);
    this._types.push(type);
    this._relIds.push(relId);
  }
  build() {
    const n = this._sources.length;
    const forward = this.buildCSR(n, this._sources, this._targets, this._types, this._relIds);
    const inverse = this.buildCSR(n, this._targets, this._sources, this._types, this._relIds);
    return {
      forward,
      inverse,
      getRelated: (entityId, relType, direction) => {
        const edges = direction === "forward" ? forward.getEdges(entityId, relType) : inverse.getEdges(entityId, relType);
        return edges.map((e) => e.target);
      },
      hasRelationship: (sourceId, targetId, relType) => {
        const edges = forward.getEdges(sourceId, relType);
        return edges.some((e) => e.target === targetId);
      },
      getRelationshipsBetween: (sourceId, targetId) => {
        const edges = forward.getEdges(sourceId);
        return edges.filter((e) => e.target === targetId).map((e) => ({
          relationshipId: e.relationshipId,
          type: e.type,
          typeName: RelationshipTypeToString(e.type)
        }));
      }
    };
  }
  /**
   * Build CSR (Compressed Sparse Row) using counting sort.
   * O(n) instead of O(n log n) — crucial for 12M+ edges.
   */
  buildCSR(n, keys, values, types, relIds) {
    if (n === 0) {
      return this.emptyEdges();
    }
    const countMap = /* @__PURE__ */ new Map();
    for (let i = 0; i < n; i++) {
      const k = keys[i];
      countMap.set(k, (countMap.get(k) ?? 0) + 1);
    }
    const offsets = /* @__PURE__ */ new Map();
    const counts = /* @__PURE__ */ new Map();
    const uniqueKeys = Array.from(countMap.keys()).sort((a, b) => a - b);
    let offset = 0;
    for (const k of uniqueKeys) {
      offsets.set(k, offset);
      counts.set(k, countMap.get(k));
      offset += countMap.get(k);
    }
    const edgeTargets = new Uint32Array(n);
    const edgeTypes = new Uint16Array(n);
    const edgeRelIds = new Uint32Array(n);
    const writePos = /* @__PURE__ */ new Map();
    for (const [k, o] of offsets) {
      writePos.set(k, o);
    }
    for (let i = 0; i < n; i++) {
      const k = keys[i];
      const pos = writePos.get(k);
      edgeTargets[pos] = values[i];
      edgeTypes[pos] = types[i];
      edgeRelIds[pos] = relIds[i];
      writePos.set(k, pos + 1);
    }
    return {
      offsets,
      counts,
      edgeTargets,
      edgeTypes,
      edgeRelIds,
      getEdges(entityId, type) {
        const o = offsets.get(entityId);
        if (o === void 0)
          return [];
        const c = counts.get(entityId);
        const edges = [];
        for (let i = o; i < o + c; i++) {
          if (type === void 0 || edgeTypes[i] === type) {
            edges.push({
              target: edgeTargets[i],
              type: edgeTypes[i],
              relationshipId: edgeRelIds[i]
            });
          }
        }
        return edges;
      },
      getTargets(entityId, type) {
        return this.getEdges(entityId, type).map((e) => e.target);
      },
      hasAnyEdges(entityId) {
        return offsets.has(entityId);
      }
    };
  }
  emptyEdges() {
    return {
      offsets: /* @__PURE__ */ new Map(),
      counts: /* @__PURE__ */ new Map(),
      edgeTargets: new Uint32Array(0),
      edgeTypes: new Uint16Array(0),
      edgeRelIds: new Uint32Array(0),
      getEdges: () => [],
      getTargets: () => [],
      hasAnyEdges: () => false
    };
  }
};
function RelationshipTypeToString(type) {
  const names = {
    [RelationshipType.ContainsElements]: "IfcRelContainedInSpatialStructure",
    [RelationshipType.Aggregates]: "IfcRelAggregates",
    [RelationshipType.DefinesByProperties]: "IfcRelDefinesByProperties",
    [RelationshipType.DefinesByType]: "IfcRelDefinesByType",
    [RelationshipType.AssociatesMaterial]: "IfcRelAssociatesMaterial",
    [RelationshipType.AssociatesClassification]: "IfcRelAssociatesClassification",
    [RelationshipType.AssociatesDocument]: "IfcRelAssociatesDocument",
    [RelationshipType.VoidsElement]: "IfcRelVoidsElement",
    [RelationshipType.FillsElement]: "IfcRelFillsElement",
    [RelationshipType.ConnectsPathElements]: "IfcRelConnectsPathElements",
    [RelationshipType.ConnectsElements]: "IfcRelConnectsElements",
    [RelationshipType.SpaceBoundary]: "IfcRelSpaceBoundary",
    [RelationshipType.AssignsToGroup]: "IfcRelAssignsToGroup",
    [RelationshipType.AssignsToProduct]: "IfcRelAssignsToProduct",
    [RelationshipType.ReferencedInSpatialStructure]: "IfcRelReferencedInSpatialStructure"
  };
  return names[type] || "Unknown";
}

// viewer/node_modules/@ifc-lite/data/dist/spatial-types.js
var SPATIAL_STRUCTURE_TYPE_ENUMS = [
  IfcTypeEnum.IfcProject,
  IfcTypeEnum.IfcSite,
  IfcTypeEnum.IfcBuilding,
  IfcTypeEnum.IfcBuildingStorey,
  IfcTypeEnum.IfcSpace,
  IfcTypeEnum.IfcFacility,
  IfcTypeEnum.IfcFacilityPart,
  IfcTypeEnum.IfcBridge,
  IfcTypeEnum.IfcBridgePart,
  IfcTypeEnum.IfcRoad,
  IfcTypeEnum.IfcRoadPart,
  IfcTypeEnum.IfcRailway,
  IfcTypeEnum.IfcRailwayPart,
  IfcTypeEnum.IfcMarineFacility
];
var BUILDING_LIKE_SPATIAL_TYPE_ENUMS = [
  IfcTypeEnum.IfcBuilding,
  IfcTypeEnum.IfcFacility,
  IfcTypeEnum.IfcBridge,
  IfcTypeEnum.IfcRoad,
  IfcTypeEnum.IfcRailway,
  IfcTypeEnum.IfcMarineFacility
];
var STOREY_LIKE_SPATIAL_TYPE_ENUMS = [
  IfcTypeEnum.IfcBuildingStorey
];
var SPACE_LIKE_SPATIAL_TYPE_ENUMS = [
  IfcTypeEnum.IfcSpace
];
var SPATIAL_STRUCTURE_TYPE_SET = new Set(SPATIAL_STRUCTURE_TYPE_ENUMS);
var BUILDING_LIKE_SPATIAL_TYPE_SET = new Set(BUILDING_LIKE_SPATIAL_TYPE_ENUMS);
var STOREY_LIKE_SPATIAL_TYPE_SET = new Set(STOREY_LIKE_SPATIAL_TYPE_ENUMS);
var SPACE_LIKE_SPATIAL_TYPE_SET = new Set(SPACE_LIKE_SPATIAL_TYPE_ENUMS);
var SPATIAL_STRUCTURE_TYPE_NAME_SET = new Set(SPATIAL_STRUCTURE_TYPE_ENUMS.map((type) => IfcTypeEnumToString(type)));
var BUILDING_LIKE_SPATIAL_TYPE_NAME_SET = new Set(BUILDING_LIKE_SPATIAL_TYPE_ENUMS.map((type) => IfcTypeEnumToString(type)));
function isSpatialStructureType(typeEnum) {
  return SPATIAL_STRUCTURE_TYPE_SET.has(typeEnum);
}
function isBuildingLikeSpatialType(typeEnum) {
  return BUILDING_LIKE_SPATIAL_TYPE_SET.has(typeEnum);
}
function isStoreyLikeSpatialType(typeEnum) {
  return STOREY_LIKE_SPATIAL_TYPE_SET.has(typeEnum);
}

// viewer/node_modules/@ifc-lite/data/dist/logger.js
function isDebugEnabled() {
  if (typeof localStorage !== "undefined") {
    try {
      return localStorage.getItem("IFC_DEBUG") === "true";
    } catch {
    }
  }
  if (typeof process !== "undefined" && process.env) {
    return process.env.IFC_DEBUG === "true";
  }
  return false;
}
function formatContext(ctx) {
  let prefix = `[${ctx.component}]`;
  if (ctx.operation) {
    prefix += ` ${ctx.operation}`;
  }
  if (ctx.entityId !== void 0) {
    prefix += ` #${ctx.entityId}`;
  }
  if (ctx.entityType) {
    prefix += ` (${ctx.entityType})`;
  }
  return prefix;
}
function formatError(error) {
  if (error instanceof Error) {
    return `${error.name}: ${error.message}${error.stack ? `
${error.stack}` : ""}`;
  }
  return String(error);
}
function createLogger(component) {
  return {
    /**
     * Log an error - always visible in console
     * Use for critical failures that affect functionality
     */
    error(message, error, ctx) {
      const prefix = formatContext({ component, ...ctx });
      if (error !== void 0) {
        if (ctx?.data !== void 0) {
          console.error(`${prefix} ${message}:`, formatError(error), ctx.data);
        } else {
          console.error(`${prefix} ${message}:`, formatError(error));
        }
      } else {
        if (ctx?.data !== void 0) {
          console.error(`${prefix} ${message}`, ctx.data);
        } else {
          console.error(`${prefix} ${message}`);
        }
      }
    },
    /**
     * Log a warning - always visible in console
     * Use for recoverable issues or degraded functionality
     */
    warn(message, ctx) {
      const prefix = formatContext({ component, ...ctx });
      if (ctx?.data !== void 0) {
        console.warn(`${prefix} ${message}`, ctx.data);
      } else {
        console.warn(`${prefix} ${message}`);
      }
    },
    /**
     * Log info - only visible when IFC_DEBUG=true
     * Use for general operational information
     */
    info(message, ctx) {
      if (!isDebugEnabled())
        return;
      const prefix = formatContext({ component, ...ctx });
      if (ctx?.data !== void 0) {
        console.log(`${prefix} ${message}`, ctx.data);
      } else {
        console.log(`${prefix} ${message}`);
      }
    },
    /**
     * Log debug - only visible when IFC_DEBUG=true
     * Use for detailed debugging information
     */
    debug(message, data, ctx) {
      if (!isDebugEnabled())
        return;
      const prefix = formatContext({ component, ...ctx });
      if (data !== void 0) {
        console.debug(`${prefix} ${message}`, data);
      } else {
        console.debug(`${prefix} ${message}`);
      }
    },
    /**
     * Log a caught error with context - visible when IFC_DEBUG=true
     * Use in catch blocks where the error is handled/recovered
     */
    caught(message, error, ctx) {
      if (!isDebugEnabled())
        return;
      const prefix = formatContext({ component, ...ctx });
      if (ctx?.data !== void 0) {
        console.debug(`${prefix} ${message} (recovered):`, formatError(error), ctx.data);
      } else {
        console.debug(`${prefix} ${message} (recovered):`, formatError(error));
      }
    }
  };
}

export {
  StringTable,
  IfcTypeEnum,
  PropertyValueType,
  QuantityType,
  RelationshipType,
  IfcTypeEnumFromString,
  IfcTypeEnumToString,
  EntityTableBuilder,
  PropertyTableBuilder,
  QuantityTableBuilder,
  RelationshipGraphBuilder,
  isSpatialStructureType,
  isBuildingLikeSpatialType,
  isStoreyLikeSpatialType,
  createLogger
};
//# sourceMappingURL=chunk-ALD7NFWX.js.map
