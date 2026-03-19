# Translation Feedback — ar

**44 files** validated: 29 PASS, 15 FAIL

## Files needing fixes

### `tutorials/advanced-techniques-for-qaoa.mdx` — FAIL

- **Code blocks**: Count mismatch: EN=32, TR=33
- **Heading count**: EN=15, TR=19
- **Heading anchors**: 6 anchor(s) missing
  - Line 442: "define a qiskit SparsePauliOp from the list of paulis" needs {#build-a-qaoa-circuit-with-the-swap-strategy-and-the-sat-mapping}
  - Line 641: "We can define the edge_coloring map so that RZZ gates are positioned right before SWAP gates to exploit CX cancellations" needs {#step-3-execute-using-qiskit-primitives}
  - Line 642: "We use greedy edge coloring from rustworkx to color the edges of the graph. This coloring is used to order the RZZ gates in the circuit." needs {#define-a-cvar-cost-function}
  - Line 689: "Utility functions for the evaluation of the expectation value of a measured state" needs {#step-4-post-process-and-return-result-in-desired-classical-format}
  - Line 690: "In this code, for optimization, the measured state is converted into a bit string," needs {#references}
  - ... and 1 more
- **Image paths**: Count mismatch: EN=5, TR=3
- **Link URLs**: 3 URL difference(s)
  - Missing URL: /docs/images/tutorials/advanced-techniques-for-qaoa/extracted-outputs/82ae28b3-85eb-4487-8100-1e622e93cccf-1.avif
  - Missing URL: /docs/images/tutorials/advanced-techniques-for-qaoa/extracted-outputs/e689e09e-6ca7-4154-8602-d1d954ebe80b-1.avif
  - Missing URL: https://docs.quantum.ibm.com/api/qiskit/qiskit.circuit.library.QAOAAnsatz

### `tutorials/approximate-quantum-compilation-for-time-evolution.mdx` — FAIL

- **Code blocks**: Count mismatch: EN=69, TR=70

### `tutorials/compilation-methods-for-hamiltonian-simulation-circuits.mdx` — FAIL

- **Code blocks**: Count mismatch: EN=31, TR=32

### `tutorials/dc-hex-ising.mdx` — FAIL

- **Line count**: EN=1292, TR=1611 (24.7% delta, max 15%)
- **Heading count**: EN=16, TR=15
- **Heading anchors**: 6 anchor(s) missing
  - Line 1002: "compare circuit depth of unitary and dynamic circuit implementations" needs {#transpilation-for-unitary-circuits}
  - Line 1094: "The MPS simulation below took approximately 7 minutes to run on a laptop with Apple M1 chip" needs {#compare-two-qubit-gate-depth-of-unitary-and-dynamic-circuits}
  - Line 1224: "Circuit durations is reported in the unit of `dt` which can be retrieved from `Backend` object" needs {#step-3-execute-using-qiskit-primitives}
  - Line 1251: "to visualize the circuit schedule, one can show the figure below" needs {#local-testing-mode}
  - Line 1260: "Save to a file since the figure is large" needs {#mps-simulation}
  - ... and 1 more
- **Image paths**: Count mismatch: EN=15, TR=11
- **Link URLs**: 7 URL difference(s)
  - Missing URL: /docs/images/tutorials/dc-hex-ising/extracted-outputs/36f1d72d-1.avif
  - Missing URL: /docs/images/tutorials/dc-hex-ising/extracted-outputs/639221e6-1.avif
  - Missing URL: /docs/images/tutorials/dc-hex-ising/extracted-outputs/662239cf-0.avif
  - Missing URL: /docs/images/tutorials/dc-hex-ising/extracted-outputs/8c3c633f-0.avif
  - Missing URL: /guides/local-testing-mode
  - ... and 2 more

### `tutorials/ghz-spacetime-codes.mdx` — FAIL

- **Code blocks**: Count mismatch: EN=50, TR=51
- **Heading count**: EN=12, TR=37
- **Heading anchors**: 4 anchor(s) missing
  - Line 507: "Search for the best root (yielding the shallowest GHZ)" needs {#step-3-execute-using-qiskit-primitives}
  - Line 527: "Build a GHZ starting at the best root" needs {#step-4-post-process-and-return-result-in-desired-classical-format}
  - Line 629: "--- Tunables controlling the search space / scoring ---" needs {#discussion}
  - Line 637: "Remove random nodes from the GHZ and build from the root again to increase checks" needs {#references}
- **Image paths**: Count mismatch: EN=12, TR=7
- **Link URLs**: 5 URL difference(s)
  - Missing URL: /docs/images/tutorials/error-detection/extracted-outputs/0c4b279b-0.avif
  - Missing URL: /docs/images/tutorials/error-detection/extracted-outputs/78c8c2b6-0.avif
  - Missing URL: /docs/images/tutorials/error-detection/extracted-outputs/b905e875-1.avif
  - Missing URL: /docs/images/tutorials/error-detection/extracted-outputs/d0faf114-0.avif
  - Missing URL: /docs/images/tutorials/error-detection/extracted-outputs/d7902975-0.avif

### `tutorials/krylov-quantum-diagonalization.mdx` — FAIL

- **LaTeX blocks ($$)**: EN=68, TR=28 (delta 40)
- **Inline LaTeX ($)**: EN=320, TR=182 (delta 138, max 30)
- **Heading count**: EN=26, TR=25
- **Heading anchors**: 3 anchor(s) missing
  - Line 849: "Distribute entries from first row across matrix:" needs {#appendix-krylov-subspace-from-real-time-evolutions}
  - Line 890: "Assemble S, the overlap matrix of dimension D:" needs {#appendix-proof-of-claim-1}
  - Line 913: "Distribute entries from first row across matrix:" needs {#references}
- **Image paths**: Count mismatch: EN=9, TR=8
- **Link URLs**: 3 URL difference(s)
  - Missing URL: /docs/images/tutorials/krylov-quantum-diagonalization/extracted-outputs/4bc52594-0376-497f-8a61-0949415a1fe0-0.avif
  - Missing URL: https://arxiv.org/abs/2407.14431
  - Missing URL: https://your.feedback.ibm.com/jfe/form/SV_82nennpKIjjD8rQ

### `tutorials/long-range-entanglement.mdx` — FAIL

- **Line count**: EN=971, TR=1207 (24.3% delta, max 15%)
- **Heading count**: EN=20, TR=24
- **Heading anchors**: 7 anchor(s) missing
  - Line 469: "Set up access to IBM Quantum devices" needs {#use-layer-fidelity-string-for-selecting-1d-chain}
  - Line 491: "This selects best qubits for longest distance and uses the same control for all lengths" needs {#visualize-qubits-used-for-the-lrcx-circuit}
  - Line 526: "Using the same initial layouts for both circuits for better apples to apples comparison" needs {#step-3-execute-using-qiskit-primitives}
  - Line 591: "Note: the qubit coordinates must be hard-coded." needs {#step-4-post-process-and-return-result-in-desired-classical-format}
  - Line 592: "The backend API does not currently provide this information directly." needs {#quality-metrics}
  - ... and 2 more
- **Image paths**: Count mismatch: EN=15, TR=11
- **Link URLs**: 4 URL difference(s)
  - Missing URL: /docs/images/tutorials/long-range-entanglement/extracted-outputs/2d090f8a-0.avif
  - Missing URL: /docs/images/tutorials/long-range-entanglement/extracted-outputs/7e5fc240-1.avif
  - Missing URL: /docs/images/tutorials/long-range-entanglement/extracted-outputs/c77c3fd3-1.avif
  - Missing URL: /docs/images/tutorials/long-range-entanglement/extracted-outputs/d6154b1c-1.avif

### `tutorials/multi-product-formula.mdx` — FAIL

- **Code blocks**: Count mismatch: EN=71, TR=72
- **LaTeX blocks ($$)**: EN=24, TR=16 (delta 8)
- **Inline LaTeX ($)**: EN=322, TR=238 (delta 84, max 30)
- **Heading count**: EN=26, TR=29
- **Heading anchors**: 16 anchor(s) missing
  - Line 532: "Create approximate time-evolution circuits" needs {#optimize-for-x-using-an-exact-model}
  - Line 538: "Find layers in the circuit" needs {#optimize-for-x-using-an-approximate-model}
  - Line 541: "Create tensor network models" needs {#dynamic-mpf-coefficients}
  - Line 546: "Create the time-evolution object" needs {#step-1-map-classical-inputs-to-a-quantum-problem}
  - Line 663: "Get expectation values at all times for each Trotter step" needs {#set-up-the-trotter-circuits}
  - ... and 11 more
- **Image paths**: Count mismatch: EN=8, TR=7
- **JSX tags**: 1 tag count mismatch(es)
  - Admonition: EN=1, TR=0
- **Link URLs**: 12 URL difference(s)
  - Missing URL: /docs/images/tutorials/multi-product-formula/extracted-outputs/2da9c948-0.avif
  - Missing URL: https://arxiv.org/abs/2407.17405
  - Missing URL: https://docs.quantum.ibm.com/api/qiskit-addon-utils/problem-generators
  - Missing URL: https://qiskit.github.io/qiskit-addon-mpf/apidocs/qiskit_addon_mpf.backends.html#qiskit_addon_mpf.backends.Evolver
  - Missing URL: https://qiskit.github.io/qiskit-addon-mpf/apidocs/qiskit_addon_mpf.backends.tenpy_layers.html#module-qiskit_addon_mpf.backends.tenpy_layers
  - ... and 7 more

### `tutorials/probabilistic-error-amplification.mdx` — FAIL

- **Code blocks**: Count mismatch: EN=32, TR=33
- **Heading count**: EN=25, TR=28
- **Heading anchors**: 9 anchor(s) missing
  - Line 403: "الخطوة 2: تحسين المسألة لتنفيذها على العتاد الكمي" needs {#isa-circuit}
  - Line 427: "المقاييس الرصدية لـ ISA" needs {#step-3-execute-using-qiskit-primitives}
  - Line 449: "الخطوة 3: التنفيذ باستخدام أوليات Qiskit" needs {#configure-estimator-options}
  - Line 455: "ضبط خيارات Estimator" needs {#explanation-of-zne-options}
  - Line 506: "شرح خيارات ZNE" needs {#run-the-experiment}
  - ... and 4 more
- **Image paths**: Count mismatch: EN=11, TR=9
- **Link URLs**: 3 URL difference(s)
  - Missing URL: /docs/images/tutorials/probabilistic-error-amplification/extracted-outputs/2e0f0e84-32ba-4655-91c1-8445016bbeb2-0.avif
  - Missing URL: /docs/images/tutorials/probabilistic-error-amplification/extracted-outputs/6948475c-bc15-493f-8af9-f8e66d0e467c-0.avif
  - Missing URL: https://your.feedback.ibm.com/jfe/form/SV_9z7nltLeb5cX9Cm

### `tutorials/projected-quantum-kernels.mdx` — FAIL

- **Line count**: EN=1017, TR=1464 (44.0% delta, max 15%)
- **Heading count**: EN=14, TR=58
- **Heading anchors**: 6 anchor(s) missing
  - Line 475: "Let's select the ZZFeatureMap embedding for this example" needs {#step-4-post-process-and-return-result-in-desired-classical-format}
  - Line 479: "Identity operator on all qubits" needs {#define-the-projected-quantum-kernel}
  - Line 482: "Let's select the first training datapoint as an example" needs {#support-vector-machine-svm}
  - Line 485: "Bind parameter to the circuit and simplify it" needs {#classical-benchmarking}
  - Line 492: "Transpile for hardware" needs {#appendix-verify-the-datasets-potential-quantum-advantage-in-learning-tasks}
  - ... and 1 more
- **Image paths**: Count mismatch: EN=3, TR=2
- **Link URLs**: 2 URL difference(s)
  - Missing URL: /docs/images/tutorials/projected-quantum-kernels/extracted-outputs/4f573436-ec5c-451b-976c-ad718b3c201d-1.avif
  - Missing URL: https://www.science.org/doi/full/10.1126/science.abq0225

### `tutorials/readout-error-mitigation-sampler.mdx` — FAIL

- **Code blocks**: Count mismatch: EN=45, TR=46

### `tutorials/sample-based-quantum-diagonalization.mdx` — FAIL

- **Line count**: EN=693, TR=931 (34.3% delta, max 15%)
- **Heading count**: EN=13, TR=23
- **Heading anchors**: 4 anchor(s) missing
  - Line 582: "without PRE_INIT passes" needs {#step-3-execute-using-qiskit-primitives}
  - Line 586: "with PRE_INIT passes" needs {#step-4-post-process-and-return-result-in-desired-classical-format}
  - Line 587: "We will use the circuit generated by this pass manager for hardware execution" needs {#visualize-the-results}
  - Line 675: "SQD options" needs {#tutorial-survey}
- **Image paths**: Count mismatch: EN=4, TR=3
- **Link URLs**: 4 URL difference(s)
  - Missing URL: /docs/images/tutorials/sample-based-quantum-diagonalization/extracted-outputs/caffd888-e89c-4aa9-8bae-4d1bb723b35e-0.avif
  - Missing URL: /guides/execution-modes
  - Missing URL: https://docs.quantum.ibm.com/api/qiskit-addon-sqd/fermion#diagonalize_fermionic_hamiltonian
  - Missing URL: https://your.feedback.ibm.com/jfe/form/SV_8cECHVBBWBjt72S

### `tutorials/shors-algorithm.mdx` — FAIL

- **Link URLs**: 1 URL difference(s)
  - Missing URL: https://doi.org/10.22331/q-2021-04-15-433

### `tutorials/sml-classification.mdx` — FAIL

- **Heading count**: EN=23, TR=19
- **Heading anchors**: 4 anchor(s) missing
  - Line 430: "Problem scale and regularization" needs {#regularization}
  - Line 463: "----- Quantum-enhanced ensemble on IBM hardware -----" needs {#step-4-post-process-and-return-result-in-desired-classical-format}
  - Line 554: "Classical baseline" needs {#evaluate-metrics-for-each-configuration}
  - Line 566: "Quantum runs" needs {#visualize-quality-trends-across-configurations}
- **Image paths**: Count mismatch: EN=1, TR=0
- **Link URLs**: 4 URL difference(s)
  - Missing URL: /docs/images/tutorials/sml-classification/extracted-outputs/0f15c5fb-2450-4671-9bc2-471043414df2-0.avif
  - Missing URL: /guides/functions
  - Missing URL: /guides/multiverse-computing-singularity
  - Missing URL: https://your.feedback.ibm.com/jfe/form/SV_3BLFkNVEuh0QBWm

### `tutorials/solve-market-split-problem-with-iskay-quantum-optimizer.mdx` — FAIL

- **Code blocks**: Count mismatch: EN=17, TR=18

## Passing files

- `tutorials/ai-transpiler-introduction.mdx`
- `tutorials/chsh-inequality.mdx`
- `tutorials/colibritd-pde.mdx`
- `tutorials/combine-error-mitigation-techniques.mdx`
- `tutorials/depth-reduction-with-circuit-cutting.mdx`
- `tutorials/edc-cut-bell-pair-benchmarking.mdx`
- `tutorials/error-mitigation-with-qiskit-functions.mdx`
- `tutorials/fractional-gates.mdx`
- `tutorials/global-data-quantum-optimizer.mdx`
- `tutorials/grovers-algorithm.mdx`
- `tutorials/hello-world.mdx`
- `tutorials/index.mdx`
- `tutorials/nishimori-phase-transition.mdx`
- `tutorials/operator-back-propagation.mdx`
- `tutorials/pauli-correlation-encoding-for-qaoa.mdx`
- `tutorials/periodic-boundary-conditions-with-circuit-cutting.mdx`
- `tutorials/qedma-2d-ising-with-qesem.mdx`
- `tutorials/quantum-approximate-optimization-algorithm.mdx`
- `tutorials/quantum-kernel-training.mdx`
- `tutorials/quantum-phase-estimation-qctrl.mdx`
- `tutorials/qunova-hivqe.mdx`
- `tutorials/real-time-benchmarking-for-qubit-selection.mdx`
- `tutorials/repetition-codes.mdx`
- `tutorials/sample-based-krylov-quantum-diagonalization.mdx`
- `tutorials/solve-higher-order-binary-optimization-problems-with-q-ctrls-optimization-solver.mdx`
- `tutorials/spin-chain-vqe.mdx`
- `tutorials/transpilation-optimizations-with-sabre.mdx`
- `tutorials/transverse-field-ising-model.mdx`
- `tutorials/wire-cutting.mdx`
