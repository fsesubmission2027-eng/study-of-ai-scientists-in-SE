# Task: ASE-2025-005 — Automated Conformance Test Generation for WebAssembly Engines

## Background

WebAssembly (Wasm) is a low-level binary format for safe, portable execution, with a formal specification defining syntax, validation, and semantics. As the language evolves with new proposals (SIMD, threads, GC, etc.), testing implementations for conformance becomes increasingly complex. Manual test suites are labor-intensive, and existing fuzzers like wasm-smith generate valid modules but rely on hard-coded validation logic that must be updated for each new feature or engine subset. A mechanized specification DSL called SpecTec now formally expresses the Wasm specification, enabling machine-readable definitions, but existing test generators do not leverage this to automatically derive tests that adapt to feature variations. The gap is the lack of a test generation framework that can automatically produce valid, diverse test cases from such mechanized specifications, tailored to the specific feature sets of different Wasm engines.

## Research Question

How can a test generation framework automatically produce valid and diverse WebAssembly test cases from a mechanized formal specification, and adapt to varying feature subsets supported by different engines?

## Experiment Setup

### Datasets
```
- name: Mechanized Wasm Specification (SpecTec format)
  source: The SpecTec project repository, which includes the DSL and the Wasm 3.0 draft specification. Can be constructed by checking out the SpecTec sources and building the specification.
  description: Formal specification of Wasm syntax, validation rules, and runtime semantics in SpecTec DSL, covering proposals like SIMD, threads, GC, etc.
  access: constructable
- name: Engine-specific specification subsets
  source: Derived from the full specification by excluding unsupported features according to engine documentation.
  description: Customized specifications for engines like V8, SpiderMonkey, JavaScriptCore, Wasmtime, Wasmer, each supporting different Wasm feature combinations.
  access: constructable
```

### Baselines
```
- name: Official Wasm conformance test suite
  reference: WebAssembly/spec repository on GitHub (tests corresponding to Wasm 3.0 draft)
```

### Metrics
```
- name: Bugs found
  definition: Number of previously unknown, confirmed bugs in real-world Wasm engines uncovered during testing.
- name: Test validity rate
  definition: Percentage of generated test cases that are deemed valid by the official Wasm reference interpreter.
- name: Specification coverage
  definition: Percentage of instruction-level abstract syntax (AL) nodes in the specification's indirect interpreter that are exercised by the test suite.
```

### Sub-questions
```
- RQ1: How many previously unknown bugs can the generated tests find in real-world Wasm engines?
- RQ2: What proportion of the generated tests are valid according to the official reference interpreter?
- RQ3: How does the specification coverage of the generated tests compare to that of the official hand-written test suite?
```

### Target Subject

WebAssembly runtimes: major engines such as V8 (Chrome), SpiderMonkey (Firefox), JavaScriptCore (Safari), Wasmtime, and Wasmer. Different engines support different subsets of the Wasm 3.0 draft.

### Constraints

Test generation and execution must be conducted within a 24-hour time budget per engine, with a 3-second timeout for generating and executing each test. Tests must be generated from the specification written in SpecTec, without manually encoding engine-specific features. The environment is Ubuntu 20.04 with 32 GB RAM.

## Expected Artifacts

- idea
- code
- experiment_results
- paper

## Feasibility Notes

The mechanized Wasm specification in SpecTec is publicly available, and all target engines are open-source. Building the test generator requires integration with SpecTec's OCaml codebase, which may present a learning curve. The compute requirements are moderate (single multi-core server, ~24 hours per engine). The primary technical challenge lies in correctly deriving engine-specific specification subsets and ensuring the generator respects all validation rules without manual tuning.

## Metadata

```
subfield: Automated Testing & Test Generation
venue: ASE 2025
year: 2025
difficulty: medium
paper_type: tool
award: ACM SIGSOFT Distinguished Paper Award
```