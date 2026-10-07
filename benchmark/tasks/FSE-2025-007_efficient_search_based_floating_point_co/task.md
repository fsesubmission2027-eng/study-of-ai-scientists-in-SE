# Task: FSE-2025-007 — Efficient Search-Based Floating-Point Constraint Solving Using Multiple Fitness Criteria

## Background

Floating-point constraint solving is essential for software testing, symbolic execution, and program verification, but faces unique challenges due to the complex semantics of floating-point arithmetic. Existing approaches fall into three categories: real arithmetic solvers (fast but imprecise and inexpressive for bitwise operations), bit-vector-based SMT solvers (precise but suffer from scalability due to NP-hard SAT encoding), and search-based solvers (heuristic, potentially scalable, but typically rely on a single scoring function, causing them to prematurely discard promising intermediate solutions). This gap motivates the need for more effective search strategies that can better navigate the large and discontinuous solution spaces of floating-point constraints without sacrificing precision.

## Research Question

How can search-based floating-point constraint solvers be made more efficient and robust by employing multiple heuristic evaluation criteria to guide the optimization process?

## Experiment Setup

### Datasets
```
- name: SMT-COMP 2023 QF_FP Benchmark
  source: https://smt-comp.github.io/2023/benchmarks.html (QF_FP logic division)
  description: A large collection of floating-point satisfiability instances from the 2023 SMT competition, containing linear and non-linear operations.
  access: open
- name: Real-World Floating-Point Program Benchmark
  source: Constructable using KLEE 2.3 symbolic executor and the GNU Scientific Library (GSL) source code (https://www.gnu.org/software/gsl/).
  description: Path constraints extracted from 252 C programs in GSL by symbolically executing each function and collecting the path conditions as floating-point constraint instances.
  access: constructable
```

### Baselines
```
- name: Z3
  reference: https://github.com/Z3Prover/z3 (de Moura & Bjørner, TACAS 2008)
- name: MathSAT5
  reference: https://mathsat.fbk.eu/ (Griggio et al., FMCAD 2015)
- name: CVC5
  reference: https://cvc5.github.io/ (Barbosa et al., TACAS 2022)
- name: Bitwuzla
  reference: https://bitwuzla.github.io/ (Schoisswohl et al., CAV 2023)
- name: goSAT
  reference: Search-based floating-point solver (paper referenced in the source study)
- name: JFS
  reference: Search-based floating-point solver (paper referenced in the source study)
- name: COLIBRI
  reference: Search-based solver (paper referenced in the source study)
- name: CORAL
  reference: Real arithmetic SMT-based solver (paper referenced in the source study)
- name: XSat
  reference: Search-based solver (paper referenced in the source study)
```

### Metrics
```
- name: Solved instances
  definition: Number of constraint instances for which the solver returns a correct satisfying assignment within the given time budget.
- name: Execution time
  definition: Wall-clock time taken by the solver to find a solution or declare failure/timeout.
- name: Winning rate
  definition: For a pair of solvers, the fraction of instances where one solver is strictly faster than the other under the same time limit.
- name: Branch coverage
  definition: Number of branches covered in the target program during symbolic execution within a fixed total analysis time, using the solver as the constraint resolution backend.
```

### Sub-questions
```
- RQ1: How effective is the proposed multi-indicator search approach compared to state-of-the-art solvers on standard floating-point constraint benchmarks?
- RQ2: How well does it perform on constraints extracted from real-world floating-point software, and what impact does it have on symbolic execution branch coverage?
- RQ3: What is the contribution of using multiple fitness criteria versus a single fitness criterion, and how do different algorithmic design choices influence overall performance?
```

### Target Subject

Floating-point constraint solving problem instances from SMT competition benchmarks and from real-world numerical software (e.g., GNU Scientific Library). The tasks include standalone solving and integration into a symbolic executor (KLEE).

### Constraints

The method must be a search-based heuristic and not rely on encoding floating-point constraints into SAT or using imprecise real arithmetic. The solver must adhere to 60-second and 600-second per-instance time limits. When integrated with KLEE, the total symbolic execution time per program is 1 hour with a 60-second solver timeout per query. All baselines and the proposed approach must be evaluated under identical machine conditions.

## Expected Artifacts

- idea
- code
- experiment_results
- paper

## Feasibility Notes

The SMT-COMP 2023 QF_FP benchmark is publicly available. The real-world GSL benchmark can be reconstructed with moderate effort using the provided KLEE scripts and GSL source code. Running all comparisons against nine baselines may require substantial CPU time (expected several hundred core-hours), but the workload is embarrassingly parallel and can be distributed. The primary challenge lies in implementing an efficient search engine that handles floating-point mutation and solution evaluation without falling into local optima, which is nontrivial but does not require specialized hardware beyond standard CPU cores.

## Metadata

```
subfield: Program Analysis & Verification
venue: FSE 2025
year: 2025
difficulty: hard
paper_type: tool
award: ACM SIGSOFT Distinguished Paper Award
```