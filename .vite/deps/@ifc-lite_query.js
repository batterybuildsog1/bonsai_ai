import {
  extractAllEntityAttributes,
  extractEntityAttributesOnDemand,
  extractPropertiesOnDemand,
  extractQuantitiesOnDemand
} from "./chunk-G5TDDLNF.js";
import {
  IfcTypeEnumFromString,
  IfcTypeEnumToString,
  PropertyValueType,
  QuantityType,
  RelationshipType
} from "./chunk-ALD7NFWX.js";

// viewer/node_modules/@ifc-lite/query/dist/property-table.js
var PropertyTable = class {
  propertySets;
  entityPropertyMap;
  // entityId -> [propertySetId, ...]
  constructor() {
    this.propertySets = /* @__PURE__ */ new Map();
    this.entityPropertyMap = /* @__PURE__ */ new Map();
  }
  /**
   * Add property set
   */
  addPropertySet(id, propertySet) {
    this.propertySets.set(id, propertySet);
  }
  /**
   * Associate property set with entity
   */
  associatePropertySet(entityId, propertySetId) {
    let sets = this.entityPropertyMap.get(entityId);
    if (!sets) {
      sets = [];
      this.entityPropertyMap.set(entityId, sets);
    }
    sets.push(propertySetId);
  }
  /**
   * Get property value for entity
   */
  getProperty(entityId, propertySetName, propertyName) {
    const propertySetIds = this.entityPropertyMap.get(entityId);
    if (!propertySetIds)
      return null;
    for (const setId of propertySetIds) {
      const pset = this.propertySets.get(setId);
      if (pset && pset.name === propertySetName) {
        return pset.properties.get(propertyName) || null;
      }
    }
    return null;
  }
  /**
   * Get all properties for entity
   */
  getProperties(entityId) {
    const result = /* @__PURE__ */ new Map();
    const propertySetIds = this.entityPropertyMap.get(entityId);
    if (!propertySetIds)
      return result;
    for (const setId of propertySetIds) {
      const pset = this.propertySets.get(setId);
      if (pset) {
        result.set(pset.name, pset);
      }
    }
    return result;
  }
  /**
   * Find entities with property matching value
   */
  findEntities(propertySetName, propertyName, value) {
    const results = [];
    for (const [entityId, propertySetIds] of this.entityPropertyMap) {
      for (const setId of propertySetIds) {
        const pset = this.propertySets.get(setId);
        if (pset && pset.name === propertySetName) {
          const prop = pset.properties.get(propertyName);
          if (prop && prop.value === value) {
            results.push(entityId);
            break;
          }
        }
      }
    }
    return results;
  }
};

// viewer/node_modules/@ifc-lite/query/dist/entity-table.js
var EntityTable = class {
  entities;
  index;
  constructor(entities, index) {
    this.entities = entities;
    this.index = index;
  }
  /**
   * Get entity by ID
   */
  getEntity(id) {
    return this.entities.get(id) || null;
  }
  /**
   * Get entities by type
   */
  getEntitiesByType(type) {
    const ids = this.index.byType.get(type) || [];
    return ids.map((id) => this.entities.get(id)).filter((e) => e !== void 0);
  }
  /**
   * Check if entity exists
   */
  hasEntity(id) {
    return this.entities.has(id);
  }
  /**
   * Get all entities
   */
  getAllEntities() {
    return Array.from(this.entities.values());
  }
};

// viewer/node_modules/@ifc-lite/query/dist/fluent-api.js
var QueryBuilder = class {
  entityTable;
  propertyTable;
  currentFilter;
  constructor(entityTable, propertyTable) {
    this.entityTable = entityTable;
    this.propertyTable = propertyTable;
    this.currentFilter = () => true;
  }
  /**
   * Filter by entity type
   */
  ofType(type) {
    const previousFilter = this.currentFilter;
    this.currentFilter = (entity) => previousFilter(entity) && entity.type === type;
    return this;
  }
  /**
   * Filter by property value
   */
  withProperty(propertySetName, propertyName, value) {
    const previousFilter = this.currentFilter;
    if (value !== void 0) {
      this.currentFilter = (entity) => {
        if (!previousFilter(entity))
          return false;
        const prop = this.propertyTable.getProperty(entity.expressId, propertySetName, propertyName);
        return prop !== null && prop.value === value;
      };
    } else {
      this.currentFilter = (entity) => {
        if (!previousFilter(entity))
          return false;
        const prop = this.propertyTable.getProperty(entity.expressId, propertySetName, propertyName);
        return prop !== null;
      };
    }
    return this;
  }
  /**
   * Execute query
   */
  execute() {
    const allEntities = this.entityTable.getAllEntities();
    return allEntities.filter(this.currentFilter);
  }
};
var QueryInterface = class {
  entityTable;
  propertyTable;
  constructor(entityTable, propertyTable) {
    this.entityTable = entityTable;
    this.propertyTable = propertyTable;
  }
  /**
   * Start a new query
   */
  query() {
    return new QueryBuilder(this.entityTable, this.propertyTable);
  }
  /**
   * Get entity by ID
   */
  getEntity(id) {
    return this.entityTable.getEntity(id);
  }
  /**
   * Get properties for entity
   */
  getProperties(entityId) {
    return this.propertyTable.getProperties(entityId);
  }
};

// viewer/node_modules/@ifc-lite/query/dist/entity-node.js
var EntityNode = class _EntityNode {
  store;
  expressId;
  _cachedAttributes = null;
  constructor(store, expressId) {
    this.store = store;
    this.expressId = expressId;
  }
  /**
   * Get on-demand extracted attributes (cached for performance)
   * Only extracts if stored values are empty and source buffer is available
   */
  getOnDemandAttributes() {
    if (this._cachedAttributes) {
      return this._cachedAttributes;
    }
    const attrs = this.store.source && this.store.entityIndex ? extractEntityAttributesOnDemand(this.store, this.expressId) : { globalId: "", name: "", description: "", objectType: "", tag: "" };
    this._cachedAttributes = attrs;
    return attrs;
  }
  get globalId() {
    const stored = this.store.entities.getGlobalId(this.expressId);
    if (stored)
      return stored;
    return this.getOnDemandAttributes().globalId;
  }
  get name() {
    const stored = this.store.entities.getName(this.expressId);
    if (stored)
      return stored;
    return this.getOnDemandAttributes().name;
  }
  get description() {
    const stored = this.store.entities.getDescription(this.expressId);
    if (stored)
      return stored;
    return this.getOnDemandAttributes().description;
  }
  get objectType() {
    const stored = this.store.entities.getObjectType(this.expressId);
    if (stored)
      return stored;
    return this.getOnDemandAttributes().objectType;
  }
  get tag() {
    return this.getOnDemandAttributes().tag;
  }
  /**
   * Get all named string/enum attributes for this entity.
   * Uses the IFC schema to determine attribute names per entity type.
   * Skips GlobalId (shown separately), OwnerHistory, and geometry references.
   */
  allAttributes() {
    if (this.store.source && this.store.entityIndex) {
      return extractAllEntityAttributes(this.store, this.expressId);
    }
    const attrs = [];
    if (this.name)
      attrs.push({ name: "Name", value: this.name });
    if (this.description)
      attrs.push({ name: "Description", value: this.description });
    if (this.objectType)
      attrs.push({ name: "ObjectType", value: this.objectType });
    if (this.tag)
      attrs.push({ name: "Tag", value: this.tag });
    return attrs;
  }
  get type() {
    return this.store.entities.getTypeName(this.expressId);
  }
  // Spatial containment
  contains() {
    return this.getRelated(RelationshipType.ContainsElements, "forward");
  }
  containedIn() {
    const nodes = this.getRelated(RelationshipType.ContainsElements, "inverse");
    return nodes[0] ?? null;
  }
  // Aggregation
  decomposes() {
    return this.getRelated(RelationshipType.Aggregates, "forward");
  }
  decomposedBy() {
    const nodes = this.getRelated(RelationshipType.Aggregates, "inverse");
    return nodes[0] ?? null;
  }
  // Types
  definingType() {
    const nodes = this.getRelated(RelationshipType.DefinesByType, "forward");
    return nodes[0] ?? null;
  }
  instances() {
    return this.getRelated(RelationshipType.DefinesByType, "inverse");
  }
  // Openings
  voids() {
    return this.getRelated(RelationshipType.VoidsElement, "forward");
  }
  filledBy() {
    return this.getRelated(RelationshipType.FillsElement, "inverse");
  }
  // Multi-hop traversal
  traverse(relType, depth, direction = "forward") {
    const visited = /* @__PURE__ */ new Set();
    const result = [];
    const visit = (nodeId, currentDepth) => {
      if (currentDepth > depth || visited.has(nodeId))
        return;
      visited.add(nodeId);
      if (nodeId !== this.expressId) {
        result.push(new _EntityNode(this.store, nodeId));
      }
      const edges = direction === "forward" ? this.store.relationships.forward.getEdges(nodeId, relType) : this.store.relationships.inverse.getEdges(nodeId, relType);
      for (const edge of edges) {
        visit(edge.target, currentDepth + 1);
      }
    };
    visit(this.expressId, 0);
    return result;
  }
  // Spatial shortcuts
  building() {
    let current = this;
    const visited = /* @__PURE__ */ new Set();
    while (current && !visited.has(current.expressId)) {
      visited.add(current.expressId);
      if (current.type === "IfcBuilding")
        return current;
      current = current.containedIn() ?? current.decomposedBy();
    }
    return null;
  }
  storey() {
    let current = this;
    const visited = /* @__PURE__ */ new Set();
    while (current && !visited.has(current.expressId)) {
      visited.add(current.expressId);
      if (current.type === "IfcBuildingStorey")
        return current;
      current = current.containedIn() ?? current.decomposedBy();
    }
    return null;
  }
  // Data access - uses on-demand extraction when available (preferred)
  properties() {
    if (this.store.onDemandPropertyMap) {
      return extractPropertiesOnDemand(this.store, this.expressId);
    }
    return this.store.properties.getForEntity(this.expressId);
  }
  property(psetName, propName) {
    if (this.store.onDemandPropertyMap && !this.store.properties.getForEntity(this.expressId).length) {
      const props = this.properties();
      const pset = props.find((p) => p.name === psetName);
      const prop = pset?.properties.find((p) => p.name === propName);
      return prop?.value ?? null;
    }
    return this.store.properties.getPropertyValue(this.expressId, psetName, propName);
  }
  quantities() {
    if (this.store.onDemandQuantityMap) {
      return extractQuantitiesOnDemand(this.store, this.expressId);
    }
    return this.store.quantities.getForEntity(this.expressId);
  }
  quantity(qsetName, quantityName) {
    if (this.store.onDemandQuantityMap && !this.store.quantities.getForEntity(this.expressId).length) {
      const qsets = this.quantities();
      const qset = qsets.find((q) => q.name === qsetName);
      const qty = qset?.quantities.find((q) => q.name === quantityName);
      return qty?.value ?? null;
    }
    return this.store.quantities.getQuantityValue(this.expressId, qsetName, quantityName);
  }
  getRelated(relType, direction) {
    const targets = this.store.relationships.getRelated(this.expressId, relType, direction);
    return targets.map((id) => new _EntityNode(this.store, id));
  }
};

// viewer/node_modules/@ifc-lite/query/dist/query-result-entity.js
var QueryResultEntity = class {
  store;
  expressId;
  // Cached data (loaded eagerly when includeFlags are set)
  _properties;
  _quantities;
  _geometry;
  constructor(store, expressId, _includeFlags) {
    this.store = store;
    this.expressId = expressId;
  }
  get globalId() {
    return this.store.entities.getGlobalId(this.expressId);
  }
  get name() {
    return this.store.entities.getName(this.expressId);
  }
  get type() {
    return this.store.entities.getTypeName(this.expressId);
  }
  get properties() {
    if (this._properties !== void 0) {
      return this._properties;
    }
    return this.store.properties.getForEntity(this.expressId);
  }
  get quantities() {
    if (this._quantities !== void 0) {
      return this._quantities;
    }
    if (this.store.quantities) {
      return this.store.quantities.getForEntity(this.expressId);
    }
    return [];
  }
  get geometry() {
    if (this._geometry !== void 0) {
      return this._geometry;
    }
    return null;
  }
  getProperty(psetName, propName) {
    return this.store.properties.getPropertyValue(this.expressId, psetName, propName);
  }
  loadProperties() {
    if (this._properties === void 0) {
      this._properties = this.store.properties.getForEntity(this.expressId);
    }
  }
  loadQuantities() {
    if (this._quantities === void 0 && this.store.quantities) {
      this._quantities = this.store.quantities.getForEntity(this.expressId);
    } else if (this._quantities === void 0) {
      this._quantities = [];
    }
  }
  loadGeometry() {
    if (this._geometry === void 0) {
      this._geometry = null;
    }
  }
  asNode() {
    return new EntityNode(this.store, this.expressId);
  }
  toJSON() {
    return {
      expressId: this.expressId,
      globalId: this.globalId,
      name: this.name,
      type: this.type,
      properties: this.properties,
      quantities: this.quantities.length > 0 ? this.quantities : void 0
    };
  }
};

// viewer/node_modules/@ifc-lite/query/dist/entity-query.js
var EntityQuery = class {
  store;
  typeFilter;
  idFilter;
  propertyFilters = [];
  limitCount = null;
  offsetCount = 0;
  includeFlags = {};
  constructor(store, types, ids = null) {
    this.store = store;
    this.typeFilter = types;
    this.idFilter = ids;
  }
  // ═══════════════════════════════════════════════════════════════
  // FILTERING
  // ═══════════════════════════════════════════════════════════════
  whereProperty(psetName, propName, operator, value) {
    this.propertyFilters.push({ pset: psetName, prop: propName, op: operator, value });
    return this;
  }
  limit(count) {
    this.limitCount = count;
    return this;
  }
  offset(count) {
    this.offsetCount = count;
    return this;
  }
  // ═══════════════════════════════════════════════════════════════
  // EAGER LOADING
  // ═══════════════════════════════════════════════════════════════
  includeGeometry() {
    this.includeFlags.geometry = true;
    return this;
  }
  includeProperties() {
    this.includeFlags.properties = true;
    return this;
  }
  includeQuantities() {
    this.includeFlags.quantities = true;
    return this;
  }
  includeAll() {
    this.includeFlags = { geometry: true, properties: true, quantities: true };
    return this;
  }
  // ═══════════════════════════════════════════════════════════════
  // EXECUTION
  // ═══════════════════════════════════════════════════════════════
  execute() {
    let ids = this.getCandidateIds();
    ids = this.applyPropertyFilters(ids);
    if (this.offsetCount > 0) {
      ids = ids.slice(this.offsetCount);
    }
    if (this.limitCount !== null) {
      ids = ids.slice(0, this.limitCount);
    }
    const results = ids.map((id) => new QueryResultEntity(this.store, id, this.includeFlags));
    for (const result of results) {
      if (this.includeFlags.properties) {
        result.loadProperties();
      }
      if (this.includeFlags.quantities) {
        result.loadQuantities();
      }
      if (this.includeFlags.geometry) {
        result.loadGeometry();
      }
    }
    return results;
  }
  async ids() {
    let ids = this.getCandidateIds();
    ids = this.applyPropertyFilters(ids);
    if (this.offsetCount > 0)
      ids = ids.slice(this.offsetCount);
    if (this.limitCount !== null)
      ids = ids.slice(0, this.limitCount);
    return ids;
  }
  async count() {
    let ids = this.getCandidateIds();
    ids = this.applyPropertyFilters(ids);
    return ids.length;
  }
  async first() {
    const results = this.limit(1).execute();
    return results[0] ?? null;
  }
  // ═══════════════════════════════════════════════════════════════
  // PRIVATE
  // ═══════════════════════════════════════════════════════════════
  getCandidateIds() {
    if (this.idFilter)
      return [...this.idFilter];
    if (this.typeFilter) {
      const ids = [];
      for (const typeEnum of this.typeFilter) {
        ids.push(...this.store.entities.getByType(typeEnum));
      }
      return ids;
    }
    const allIds = [];
    for (let i = 0; i < this.store.entities.count; i++) {
      allIds.push(this.store.entities.expressId[i]);
    }
    return allIds;
  }
  applyPropertyFilters(ids) {
    if (this.propertyFilters.length === 0)
      return ids;
    let filteredIds = ids;
    for (const filter of this.propertyFilters) {
      const matchingIds = this.store.properties.findByProperty(filter.prop, filter.op, filter.value);
      const matchingSet = new Set(matchingIds);
      filteredIds = filteredIds.filter((id) => matchingSet.has(id));
    }
    return filteredIds;
  }
};

// viewer/node_modules/@ifc-lite/query/dist/duckdb-integration.js
var DuckDBIntegration = class {
  db = null;
  conn = null;
  initPromise = null;
  initialized = false;
  /**
   * Initialize DuckDB (lazy-loaded)
   */
  async init(store) {
    if (this.initialized)
      return;
    if (this.initPromise)
      return this.initPromise;
    this.initPromise = (async () => {
      try {
        const duckdb = await new Function('return import("@duckdb/duckdb-wasm")')();
        const bundle = await duckdb.selectBundle(duckdb.getJsDelivrBundles());
        const worker = new Worker(bundle.mainWorker);
        this.db = new duckdb.AsyncDuckDB(new duckdb.ConsoleLogger(), worker);
        await this.db.instantiate(bundle.mainModule, bundle.pthreadWorker);
        this.conn = await this.db.connect();
        await this.registerTables(store);
        await this.createViews();
        this.initialized = true;
        console.log("[DuckDB] Initialization complete");
      } catch (error) {
        throw new Error(`Failed to initialize DuckDB: ${error}`);
      }
    })();
    return this.initPromise;
  }
  /**
   * Execute SQL query
   */
  async query(sql) {
    if (!this.initialized) {
      throw new Error("DuckDB not initialized. Call init() first.");
    }
    const result = await this.conn.query(sql);
    const rows = result.toArray();
    return {
      columns: result.schema.fields.map((f) => f.name),
      rows,
      toArray: () => rows,
      toJSON: () => rows.map((row) => {
        const obj = {};
        result.schema.fields.forEach((field, i) => {
          obj[field.name] = Array.isArray(row) ? row[i] : row[field.name];
        });
        return obj;
      })
    };
  }
  /**
   * Register tables from columnar store using SQL INSERT statements
   * This approach works without Arrow dependencies and is more portable
   */
  async registerTables(store) {
    console.log("[DuckDB] Registering tables from store with", store.entities.count, "entities");
    await this.createEntitiesTable(store);
    await this.createPropertiesTable(store);
    await this.createQuantitiesTable(store);
    await this.createRelationshipsTable(store);
    console.log("[DuckDB] All tables registered successfully");
  }
  /**
   * Create and populate entities table
   */
  async createEntitiesTable(store) {
    await this.conn.query(`
      CREATE TABLE entities (
        express_id INTEGER PRIMARY KEY,
        global_id VARCHAR,
        name VARCHAR,
        description VARCHAR,
        type VARCHAR,
        object_type VARCHAR,
        has_geometry BOOLEAN,
        is_type BOOLEAN,
        contained_in_storey INTEGER,
        defined_by_type INTEGER
      )
    `);
    const { entities, strings } = store;
    const batchSize = 1e3;
    for (let i = 0; i < entities.count; i += batchSize) {
      const end = Math.min(i + batchSize, entities.count);
      const values = [];
      for (let j = i; j < end; j++) {
        const expressId = entities.expressId[j];
        const globalId = escapeSQL(strings.get(entities.globalId[j]));
        const name = escapeSQL(strings.get(entities.name[j]));
        const description = escapeSQL(strings.get(entities.description[j]));
        const type = escapeSQL(IfcTypeEnumToString(entities.typeEnum[j]));
        const objectType = escapeSQL(strings.get(entities.objectType[j]));
        const hasGeometry = (entities.flags[j] & 1) !== 0;
        const isType = (entities.flags[j] & 2) !== 0;
        const containedInStorey = entities.containedInStorey[j] || "NULL";
        const definedByType = entities.definedByType[j] || "NULL";
        values.push(`(${expressId}, '${globalId}', '${name}', '${description}', '${type}', '${objectType}', ${hasGeometry}, ${isType}, ${containedInStorey}, ${definedByType})`);
      }
      if (values.length > 0) {
        await this.conn.query(`INSERT INTO entities VALUES ${values.join(", ")}`);
      }
    }
    console.log(`[DuckDB] Registered entities table with ${entities.count} rows`);
  }
  /**
   * Create and populate properties table
   */
  async createPropertiesTable(store) {
    await this.conn.query(`
      CREATE TABLE properties (
        entity_id INTEGER,
        pset_name VARCHAR,
        pset_global_id VARCHAR,
        prop_name VARCHAR,
        prop_type VARCHAR,
        value_string VARCHAR,
        value_real DOUBLE,
        value_int INTEGER,
        value_bool BOOLEAN
      )
    `);
    const { properties, strings } = store;
    const batchSize = 1e3;
    const propTypeNames = {
      [PropertyValueType.String]: "String",
      [PropertyValueType.Real]: "Real",
      [PropertyValueType.Integer]: "Integer",
      [PropertyValueType.Boolean]: "Boolean",
      [PropertyValueType.Logical]: "Logical",
      [PropertyValueType.Label]: "Label",
      [PropertyValueType.Identifier]: "Identifier",
      [PropertyValueType.Text]: "Text",
      [PropertyValueType.Enum]: "Enum",
      [PropertyValueType.Reference]: "Reference",
      [PropertyValueType.List]: "List"
    };
    for (let i = 0; i < properties.count; i += batchSize) {
      const end = Math.min(i + batchSize, properties.count);
      const values = [];
      for (let j = i; j < end; j++) {
        const entityId = properties.entityId[j];
        const psetName = escapeSQL(strings.get(properties.psetName[j]));
        const psetGlobalId = escapeSQL(strings.get(properties.psetGlobalId[j]));
        const propName = escapeSQL(strings.get(properties.propName[j]));
        const propType = propTypeNames[properties.propType[j]] || "Unknown";
        const valueStringIdx = properties.valueString[j];
        const valueString = valueStringIdx >= 0 ? escapeSQL(strings.get(valueStringIdx)) : "";
        const valueReal = isNaN(properties.valueReal[j]) ? "NULL" : properties.valueReal[j];
        const valueInt = properties.valueInt[j];
        const valueBoolRaw = properties.valueBool[j];
        const valueBool = valueBoolRaw === 255 ? "NULL" : valueBoolRaw === 1 ? "true" : "false";
        values.push(`(${entityId}, '${psetName}', '${psetGlobalId}', '${propName}', '${propType}', '${valueString}', ${valueReal}, ${valueInt}, ${valueBool})`);
      }
      if (values.length > 0) {
        await this.conn.query(`INSERT INTO properties VALUES ${values.join(", ")}`);
      }
    }
    console.log(`[DuckDB] Registered properties table with ${properties.count} rows`);
  }
  /**
   * Create and populate quantities table
   */
  async createQuantitiesTable(store) {
    await this.conn.query(`
      CREATE TABLE quantities (
        entity_id INTEGER,
        qset_name VARCHAR,
        quantity_name VARCHAR,
        quantity_type VARCHAR,
        value DOUBLE,
        formula VARCHAR
      )
    `);
    const { quantities, strings } = store;
    const batchSize = 1e3;
    const quantTypeNames = {
      [QuantityType.Length]: "Length",
      [QuantityType.Area]: "Area",
      [QuantityType.Volume]: "Volume",
      [QuantityType.Count]: "Count",
      [QuantityType.Weight]: "Weight",
      [QuantityType.Time]: "Time"
    };
    for (let i = 0; i < quantities.count; i += batchSize) {
      const end = Math.min(i + batchSize, quantities.count);
      const values = [];
      for (let j = i; j < end; j++) {
        const entityId = quantities.entityId[j];
        const qsetName = escapeSQL(strings.get(quantities.qsetName[j]));
        const quantityName = escapeSQL(strings.get(quantities.quantityName[j]));
        const quantityType = quantTypeNames[quantities.quantityType[j]] || "Unknown";
        const value = quantities.value[j];
        const formulaIdx = quantities.formula[j];
        const formula = formulaIdx > 0 ? escapeSQL(strings.get(formulaIdx)) : "";
        values.push(`(${entityId}, '${qsetName}', '${quantityName}', '${quantityType}', ${value}, '${formula}')`);
      }
      if (values.length > 0) {
        await this.conn.query(`INSERT INTO quantities VALUES ${values.join(", ")}`);
      }
    }
    console.log(`[DuckDB] Registered quantities table with ${quantities.count} rows`);
  }
  /**
   * Create and populate relationships table
   */
  async createRelationshipsTable(store) {
    await this.conn.query(`
      CREATE TABLE relationships (
        source_id INTEGER,
        target_id INTEGER,
        rel_type VARCHAR,
        rel_id INTEGER
      )
    `);
    const { relationships } = store;
    const edges = relationships.forward;
    const batchSize = 1e3;
    const relTypeNames = {
      [RelationshipType.ContainsElements]: "ContainsElements",
      [RelationshipType.Aggregates]: "Aggregates",
      [RelationshipType.DefinesByProperties]: "DefinesByProperties",
      [RelationshipType.DefinesByType]: "DefinesByType",
      [RelationshipType.AssociatesMaterial]: "AssociatesMaterial",
      [RelationshipType.AssociatesClassification]: "AssociatesClassification",
      [RelationshipType.VoidsElement]: "VoidsElement",
      [RelationshipType.FillsElement]: "FillsElement",
      [RelationshipType.ConnectsPathElements]: "ConnectsPathElements",
      [RelationshipType.ConnectsElements]: "ConnectsElements",
      [RelationshipType.SpaceBoundary]: "SpaceBoundary",
      [RelationshipType.AssignsToGroup]: "AssignsToGroup",
      [RelationshipType.AssignsToProduct]: "AssignsToProduct",
      [RelationshipType.ReferencedInSpatialStructure]: "ReferencedInSpatialStructure"
    };
    const rows = [];
    for (const [sourceId, offset] of edges.offsets) {
      const count = edges.counts.get(sourceId) || 0;
      for (let i = offset; i < offset + count; i++) {
        rows.push({
          sourceId,
          targetId: edges.edgeTargets[i],
          relType: relTypeNames[edges.edgeTypes[i]] || "Unknown",
          relId: edges.edgeRelIds[i]
        });
      }
    }
    for (let i = 0; i < rows.length; i += batchSize) {
      const end = Math.min(i + batchSize, rows.length);
      const values = [];
      for (let j = i; j < end; j++) {
        const row = rows[j];
        values.push(`(${row.sourceId}, ${row.targetId}, '${row.relType}', ${row.relId})`);
      }
      if (values.length > 0) {
        await this.conn.query(`INSERT INTO relationships VALUES ${values.join(", ")}`);
      }
    }
    console.log(`[DuckDB] Registered relationships table with ${rows.length} rows`);
  }
  /**
   * Create convenience views
   */
  async createViews() {
    try {
      await this.conn.query(`
        CREATE VIEW IF NOT EXISTS walls AS
        SELECT * FROM entities WHERE type IN ('IfcWall', 'IfcWallStandardCase')
      `);
      await this.conn.query(`
        CREATE VIEW IF NOT EXISTS doors AS
        SELECT * FROM entities WHERE type = 'IfcDoor'
      `);
      await this.conn.query(`
        CREATE VIEW IF NOT EXISTS windows AS
        SELECT * FROM entities WHERE type = 'IfcWindow'
      `);
      await this.conn.query(`
        CREATE VIEW IF NOT EXISTS slabs AS
        SELECT * FROM entities WHERE type = 'IfcSlab'
      `);
      await this.conn.query(`
        CREATE VIEW IF NOT EXISTS columns AS
        SELECT * FROM entities WHERE type = 'IfcColumn'
      `);
      await this.conn.query(`
        CREATE VIEW IF NOT EXISTS beams AS
        SELECT * FROM entities WHERE type = 'IfcBeam'
      `);
      await this.conn.query(`
        CREATE VIEW IF NOT EXISTS spaces AS
        SELECT * FROM entities WHERE type = 'IfcSpace'
      `);
      await this.conn.query(`
        CREATE VIEW IF NOT EXISTS entity_properties AS
        SELECT
          e.express_id, e.name as entity_name, e.type as entity_type,
          p.pset_name, p.prop_name, p.prop_type,
          p.value_string, p.value_real, p.value_int, p.value_bool
        FROM entities e
        LEFT JOIN properties p ON e.express_id = p.entity_id
      `);
      await this.conn.query(`
        CREATE VIEW IF NOT EXISTS entity_quantities AS
        SELECT
          e.express_id, e.name as entity_name, e.type as entity_type,
          q.qset_name, q.quantity_name, q.quantity_type, q.value
        FROM entities e
        LEFT JOIN quantities q ON e.express_id = q.entity_id
      `);
      console.log("[DuckDB] Created convenience views");
    } catch (error) {
      console.warn("[DuckDB] Could not create views:", error);
    }
  }
  /**
   * Check if DuckDB is available
   */
  static async isAvailable() {
    try {
      await new Function('return import("@duckdb/duckdb-wasm")')();
      return true;
    } catch {
      return false;
    }
  }
  /**
   * Dispose of DuckDB resources
   */
  async dispose() {
    if (this.conn) {
      await this.conn.close();
      this.conn = null;
    }
    if (this.db) {
      await this.db.terminate();
      this.db = null;
    }
    this.initialized = false;
    this.initPromise = null;
  }
};
function escapeSQL(value) {
  if (value === null || value === void 0) {
    return "";
  }
  return value.replace(/'/g, "''");
}

// viewer/node_modules/@ifc-lite/query/dist/ifc-query.js
var IfcQuery = class {
  store;
  duckdb = null;
  constructor(store) {
    this.store = store;
  }
  // ═══════════════════════════════════════════════════════════════
  // SQL API - Full SQL power via DuckDB-WASM
  // ═══════════════════════════════════════════════════════════════
  async sql(query) {
    await this.ensureDuckDB();
    return this.duckdb.query(query);
  }
  async ensureDuckDB() {
    if (!this.duckdb) {
      const available = await DuckDBIntegration.isAvailable();
      if (!available) {
        throw new Error("DuckDB-WASM is not available. Install @duckdb/duckdb-wasm to use SQL queries.");
      }
      this.duckdb = new DuckDBIntegration();
      await this.duckdb.init(this.store);
    }
  }
  // ═══════════════════════════════════════════════════════════════
  // FLUENT API - Type-safe query builder
  // ═══════════════════════════════════════════════════════════════
  walls() {
    return this.ofType("IfcWall", "IfcWallStandardCase");
  }
  doors() {
    return this.ofType("IfcDoor");
  }
  windows() {
    return this.ofType("IfcWindow");
  }
  slabs() {
    return this.ofType("IfcSlab");
  }
  columns() {
    return this.ofType("IfcColumn");
  }
  beams() {
    return this.ofType("IfcBeam");
  }
  spaces() {
    return this.ofType("IfcSpace");
  }
  ofType(...types) {
    const typeEnums = types.map((t) => IfcTypeEnumFromString(t));
    return new EntityQuery(this.store, typeEnums);
  }
  all() {
    return new EntityQuery(this.store, null);
  }
  byId(expressId) {
    return new EntityQuery(this.store, null, [expressId]);
  }
  // ═══════════════════════════════════════════════════════════════
  // GRAPH API - Relationship traversal
  // ═══════════════════════════════════════════════════════════════
  entity(expressId) {
    return new EntityNode(this.store, expressId);
  }
  // ═══════════════════════════════════════════════════════════════
  // SPATIAL API - Geometry-based queries
  // ═══════════════════════════════════════════════════════════════
  inBounds(aabb) {
    if (!this.store.spatialIndex) {
      throw new Error("Spatial index not available. Geometry must be processed first.");
    }
    const ids = this.store.spatialIndex.queryAABB(aabb);
    return new EntityQuery(this.store, null, ids);
  }
  onStorey(storeyId) {
    if (!this.store.spatialHierarchy) {
      throw new Error("Spatial hierarchy not available.");
    }
    const ids = this.store.spatialHierarchy.byStorey.get(storeyId) ?? [];
    return new EntityQuery(this.store, null, ids);
  }
  raycast(origin, direction) {
    if (!this.store.spatialIndex) {
      throw new Error("Spatial index not available. Geometry must be processed first.");
    }
    return this.store.spatialIndex.raycast(origin, direction);
  }
  // ═══════════════════════════════════════════════════════════════
  // SPATIAL HIERARCHY ACCESS
  // ═══════════════════════════════════════════════════════════════
  get hierarchy() {
    return this.store.spatialHierarchy ?? null;
  }
  get project() {
    if (!this.store.spatialHierarchy)
      return null;
    return this.entity(this.store.spatialHierarchy.project.expressId);
  }
  get storeys() {
    if (!this.store.spatialHierarchy)
      return [];
    return [...this.store.spatialHierarchy.byStorey.keys()].sort((a, b) => {
      const elevA = this.store.spatialHierarchy.storeyElevations.get(a) ?? 0;
      const elevB = this.store.spatialHierarchy.storeyElevations.get(b) ?? 0;
      return elevA - elevB;
    }).map((id) => this.entity(id));
  }
};
export {
  DuckDBIntegration,
  EntityNode,
  EntityQuery,
  EntityTable,
  IfcQuery,
  PropertyTable,
  QueryBuilder,
  QueryInterface,
  QueryResultEntity
};
//# sourceMappingURL=@ifc-lite_query.js.map
