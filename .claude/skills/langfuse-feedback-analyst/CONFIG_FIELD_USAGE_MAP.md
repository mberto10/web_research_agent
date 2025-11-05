# Config Field Usage Map
## Fields Actually Used by the Generation Architecture

This document maps which config file fields are **actually read and used** by the generation system. Only suggest changes to these fields - other fields will be ignored.

---

## template.yaml

### Fields Read by `case_config_template.py`

#### Section Extraction (`get_required_sections()`)ThisTHIS I
Searches these paths in order (first match wins):
1. `required_sections[]` → list of strings
2. `structure.sections[]` → list of strings or dicts with .name
3. `content_structure.required_sections[]` → list of dicts with .section_name or .name, or strings
4. `content_structure.section_list[]` → list of strings
5. `template_configuration.sections[]` → list of dicts with .label or .section_id

**Used by:** Editor node to validate section presence

#### Header Format Detection (`should_use_section_headers()`)
Checks these fields to determine if markdown headers (##) are needed:
1. `template_configuration.use_section_headers` (boolean)
2. `template_configuration.template_type` → if in ["article", "narrative", "essay", "story"] = no headers
3. `content_structure.flow_pattern` → if in ["narrative_arc", "linear", "seamless"] = no headers
4. `template_definition.flow_pattern` → if in ["narrative_arc", "linear", "seamless"] = no headers
5. `template_definition.purpose.primary_goal` → if contains "without section" or "seamless" = no headers

**Used by:** Editor node to determine structural scoring

#### Other Extracted Fields
- `quality_criteria[]` → list of strings (evaluation criteria)
- `template_definition.language` or `content_structure.language` → language code (e.g., "de-DE")
- `mandatory_elements.data_requirements[]` → list of data requirement objects

### Fields Passed to Writer (Entire Template)
The entire template dict is passed to `WriterAgent` via `template_spec` parameter, so writer may access any field. Common patterns:
- `content_structure.word_count` → target word counts
- `required_sections[].word_count_range` → per-section word counts
- `required_sections[].must_include[]` → required elements per section
- `required_sections[].style_notes[]` → section-specific guidance

**Recommendation:** Keep existing template structure fields if they provide writer guidance, even if not explicitly checked by deterministic validators.

---

## style.yaml (5-Layer Schema v2.0)

### metadata
**Read by:** `CaseConfigStyleInterface`, trace tagging, check compiler
- `id` → style identifier
- `profile_name` → display name
- `schema_version` → must be "5-layer-v1"
- `extraction_confidence` → quality indicator

### constraints.metric_bounds
**Read by:** Check compiler → generates `MetricCheckSpec` objects
**All metrics compiled into checks:**
- `type_token_ratio` (min, max, target, tolerance)
- `avg_word_length` (min, max, target, tolerance)
- `punctuation_density` (min, max, target, tolerance)
- `lexical_density` (min, max, target, tolerance)
- `avg_sentence_length` (min, max, target, tolerance)
- `sentence_length_std` (min, max, target, tolerance)
- `sentence_length_skew` (min, max, target, tolerance)
- `paragraph_length_mean` (min, max, target, tolerance)
- `paragraph_length_std` (min, max, target, tolerance)
- `sentences_per_paragraph` (min, max, target, tolerance)
- `char_ngram_entropy` (min, max, target, tolerance)
- `char_distribution_entropy` (min, max, target, tolerance)
- `token_length_mean` (min, max, target, tolerance)
- `token_length_std` (min, max, target, tolerance)
- `blank_line_frequency` (min, max, target, tolerance)
- `whitespace_ratio` (min, max, target, tolerance)
- `hedging_density` (min, max, target, tolerance)
- `discourse_marker_frequency` (min, max, target, tolerance)
- `lexical_tightness` (min, max, target, tolerance)
- `char_4gram_diversity` (min, max, target, tolerance)
- `mean_dependency_distance` (min, max, target, tolerance)
- `dependency_diversity` (min, max, target, tolerance)
- `subordination_index` (min, max, target, tolerance)
- `pos_skipgram_diversity` (min, max, target, tolerance)

### constraints.lexical
**Read by:** Check compiler, style interface
- `required_terms[]` → compiled into `FrequencyCheckSpec`
  - id
  - terms (list)
  - pattern (regex)
  - min_count
  - scope
  - severity
  - reasoning
- `banned_terms[]` → compiled into `RegexCheckSpec`
  - id
  - terms (list)
  - reason
  - severity
- `preferred_vocabulary[]` → used in style instructions
- `signature_vocabulary[]` → used in style instructions
- `required_phrases[]` → used in style instructions
- `code_switching_patterns[]` → used in style instructions

### constraints.syntactic
**Read by:** Check compiler
- `sentence_structure.length` (target, min, max, tolerance)
- `sentence_structure.completeness` (require_subject_verb, min_sentence_length_words)
- `sentence_structure.variance` (target, min)
- `sentence_structure.type_distribution` (simple, compound, complex, compound_complex, tolerance)
- `required_patterns[]` (pattern, example, min_usage, reasoning)
- `forbidden_patterns[]` (pattern, regex, context, description, severity)

### constraints.formatting
**Read by:** Check compiler
- `required_structure[]` (element, pattern, min_count, severity, reasoning)
- `number_formatting[]` (rule, pattern, description, severity)
- `typography[]` (element, character, pattern, min_usage, usage, reasoning)

### signatures.tone_rubric
**Read by:** Style interface, check compiler (LLM grader)
- `primary_tones[]`
- `secondary_tones[]` (tone, when_used, weight, examples)
- `formality_level` (0-1 scale)
- `formality_description`
- `encouraged_emotions[]`
- `banned_emotions[]`
- `grader_prompt` → **CRITICAL:** This is the actual LLM grader prompt

### signatures.voice_embedding
**Read by:** Style interface
- `voice_characteristics[]` → shown to writer as guidelines
- `signature_text` → example text for voice matching

### signatures.prosodic_signature
**Read by:** Style interface
- `cadence_style`
- `rhythm_markers[]`
- `signature_devices[]`

### signatures.argumentative_structure
**Read by:** Check compiler (LLM grader)
- `grader_prompt` → LLM grader instructions
- `weight` → check importance
- `enabled` → whether check runs

### patterns.document_structure
**Read by:** Check compiler (structural checks)
- `article_sections.required[]` (name, position, word_range, must_include, pattern, severity)
- `article_sections.optional[]`
- `article_sections.allow_extra`
- `article_sections.min_word_count`
- `article_sections.max_word_count`

### patterns.structural_devices
**Read by:** Check compiler
- `<device_name>.pattern` (regex pattern)
- `<device_name>.min_usage` (frequency threshold)
- `<device_name>.scope` (where to check)
- `<device_name>.severity` (critical/major/minor)

---

## tools.yaml

### research_patterns
**Read by:** `research_node.py` via `load_case_research_patterns()`
- `default` → which pattern name to use
- `patterns.<pattern_name>.steps[]`:
  - `tool` → tool name from registry
  - `condition` → when to execute (template string)
  - `input` → tool parameters (dict with template variables)
  - `save_as` → result variable name
  - `on_error` → "abort", "continue", or "retry"
  - `description` → human-readable purpose
  - `for_each` → list path for iteration (e.g., "user.portfolio.summary.symbols")
  - `as` → loop variable name (default: "item")
  - `optional` → whether step can be skipped

### tool_configuration
**Read by:** Research agent, tool registry
- `react_agent_enabled` → enables/disables ReAct agent
- `required_tools[]` → must be available
- `optional_tools[]` → nice to have
- `tool_configurations.<tool_name>` → tool-specific settings

---

## Fields That Are IGNORED

### template.yaml - Documentation/Planning Only
These fields are NOT read by the generation system:
- `template_definition.name` → documentation only
- `template_definition.id` → documentation only
- `template_definition.category` → documentation only
- `template_definition.domain` → documentation only
- `template_definition.version` → documentation only
- `template_definition.created` → documentation only
- `purpose.secondary_goals[]` → documentation only
- `purpose.success_metrics[]` → documentation only
- `target_audience.pain_points[]` → documentation only
- `target_audience.expectations` → documentation only
- `error_handling.*` → documentation only
- `contextual_variations[]` → documentation only
- `reference_examples.*` → documentation only

### style.yaml - Documentation Only
- `dynamics.*` → not currently used by checks
- `quality_markers.*` → not used by checks
- `exemptions.*` → not used by checks
- `validation_notes.*` → documentation only

### tools.yaml - Not Implemented
- `tool_configuration.case_name` → metadata only
- `tool_configuration.configuration_version` → metadata only
- `tool_configuration.last_updated` → metadata only

---

## Recommendation Guidelines for Feedback Analysis

### ✅ DO Suggest Changes To:
1. **template.yaml:**
   - Section names in required_sections (if sections are missing/wrong)
   - word_count ranges (if content is too long/short)
   - must_include elements per section (if required content missing)
   - style_notes for section-specific guidance
   - flow_pattern / use_section_headers (if header format wrong)

2. **style.yaml:**
   - `signatures.tone_rubric.grader_prompt` → THE MOST IMPORTANT FIELD
   - `signatures.tone_rubric.primary_tones` / `secondary_tones`
   - `signatures.argumentative_structure.grader_prompt` → if logic/structure issues
   - `constraints.lexical.required_terms` → if specific terminology missing
   - `constraints.lexical.banned_terms` → if problematic phrases appear
   - `patterns.document_structure.article_sections` → if structure violations
   - `patterns.structural_devices` → if signature patterns missing
   - `constraints.metric_bounds.*` → ONLY if metrics are systematically wrong (requires data analysis)

3. **tools.yaml:**
   - `research_patterns.default.steps[]` → add/modify/remove research steps
   - Step parameters: input, save_as, description, on_error
   - Loop directives: for_each, as (if batch operations needed)

### ❌ DON'T Suggest Changes To:
1. Metadata/documentation fields (name, description, version, etc.)
2. Fields not listed in "Actually Used" sections above
3. Fields in dynamics/quality_markers/exemptions layers (not implemented)
4. Error handling / contextual variations (documentation only)

---

## Priority Hierarchy for Feedback-Driven Changes

When user feedback indicates quality issues:

### 1. HIGH IMPACT (Fix First)
- **tone_rubric.grader_prompt** → Changes tone/style scoring immediately
- **argumentative_structure.grader_prompt** → Fixes logic/flow issues
- **required_terms / banned_terms** → Prevents specific terminology errors
- **article_sections.required** → Enforces structural requirements

### 2. MEDIUM IMPACT
- **primary_tones / secondary_tones** → Adjusts voice characteristics
- **voice_characteristics** → Updates writer guidance
- **structural_devices patterns** → Enforces signature patterns
- **research_patterns steps** → Improves data quality

### 3. LOW IMPACT (Data-Driven Only)
- **metric_bounds** → Only change if statistical analysis shows systematic deviation
- **sentence_structure length/variance** → Only if measurable quality degradation
- **formatting rules** → Only if format violations are frequent

**CRITICAL:** Never suggest metric_bounds changes without statistical evidence from multiple traces showing consistent deviation from targets.
