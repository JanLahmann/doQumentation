# Translation Feedback — ro

**12 files** validated: 0 PASS, 12 FAIL

## Files needing fixes

### `guides/qiskit-backendv1-to-v2.mdx` — FAIL

- **Line count**: EN=75, TR=55 (26.7% delta, max 15%)

### `guides/runtime-options-overview.mdx` — FAIL

- **Heading count**: EN=89, TR=90
- **Heading anchors**: 52 anchor(s) missing
  - Line 367: "`resilience.pec_mitigation`" needs {#resiliencepec}
  - Line 378: "`resilience.pec`" needs {#resiliencepecmax-overhead}
  - Line 388: "`resilience.pec.max_overhead`" needs {#resiliencepecnoise-gain}
  - Line 399: "`resilience.pec.noise_gain`" needs {#resiliencezne-mitigation}
  - Line 410: "`resilience.zne_mitigation`" needs {#resiliencezne}
  - ... and 47 more

### `learning/courses/fundamentals-of-quantum-algorithms/quantum-algorithmic-foundations/measuring-computational-cost.mdx` — FAIL

- **Line count**: EN=430, TR=1 (99.8% delta, max 15%)
- **LaTeX blocks ($$)**: EN=16, TR=0 (delta 16)
- **Inline LaTeX ($)**: EN=324, TR=0 (delta 324, max 35)
- **Heading count**: EN=16, TR=0
- **Image paths**: Count mismatch: EN=6, TR=0
- **Frontmatter**: 1 issue(s)
  - Missing key: notebook_path
- **JSX tags**: 1 tag count mismatch(es)
  - Figure: EN=4, TR=0
- **Link URLs**: 6 URL difference(s)
  - Missing URL: /learning/images/courses/fundamentals-of-quantum-algorithms/quantum-algorithmic-foundations/Boolean-circuit-XOR.svg
  - Missing URL: /learning/images/courses/fundamentals-of-quantum-algorithms/quantum-algorithmic-foundations/addition-circuit.svg
  - Missing URL: /learning/images/courses/fundamentals-of-quantum-algorithms/quantum-algorithmic-foundations/deferred-measurement.svg
  - Missing URL: /learning/images/courses/fundamentals-of-quantum-algorithms/quantum-algorithmic-foundations/full-adder.svg
  - Missing URL: /learning/images/courses/fundamentals-of-quantum-algorithms/quantum-algorithmic-foundations/half-adder.svg
  - ... and 1 more

### `learning/courses/quantum-computing-in-practice/simulating-nature.mdx` — FAIL

- **Line count**: EN=314, TR=6 (98.1% delta, max 15%)
- **Code blocks**: Count mismatch: EN=1, TR=0
- **LaTeX blocks ($$)**: EN=18, TR=0 (delta 18)
- **Inline LaTeX ($)**: EN=104, TR=0 (delta 104, max 35)
- **Heading count**: EN=9, TR=0
- **Image paths**: Count mismatch: EN=12, TR=0
- **Frontmatter**: 1 issue(s)
  - Missing key: notebook_path
- **JSX tags**: 2 tag count mismatch(es)
  - Admonition: EN=1, TR=0
  - IBMVideo: EN=1, TR=0
- **Link URLs**: 23 URL difference(s)
  - Missing URL: /guides/error-mitigation-and-suppression-techniques
  - Missing URL: /learning/courses/quantum-computing-in-practice/mapping
  - Missing URL: /learning/courses/quantum-diagonalization-algorithms/krylov#31-time-evolution
  - Missing URL: /learning/images/courses/quantum-computing-in-practice/simulating-nature/bad-qubits.svg
  - Missing URL: /learning/images/courses/quantum-computing-in-practice/simulating-nature/data.svg
  - ... and 18 more

### `learning/courses/quantum-diagonalization-algorithms/krylov.mdx` — FAIL

- **Code blocks**: Count mismatch: EN=61, TR=62
- **LaTeX blocks ($$)**: EN=158, TR=122 (delta 36)
- **Inline LaTeX ($)**: EN=610, TR=334 (delta 276, max 35)
- **Indented headings**: 26 heading(s) with leading whitespace (breaks MDX)
  - Line 641: '# We have not yet found a Krylov subspace that produces our ' has 4 leading space(s)
  - Line 644: '# If we still haven't found the desired subspace...' has 8 leading space(s)
  - Line 646: '# ...but if this one satisfies the requirement, then record ' has 12 leading space(s)
  - Line 702: '# Ensure we don't exceed the boundaries of our lists' has 4 leading space(s)
  - Line 706: '# Dummy variables for accumulating an average over adjacent ' has 4 leading space(s)
  - ... and 21 more
- **Heading count**: EN=36, TR=90
- **Heading anchors**: 23 anchor(s) missing
  - Line 490: "Definim matricea noastră de test mică" needs {#22-time-scaling-with-matrix-dimension}
  - Line 501: "Transmitem matricea de test și o estimare inițială ca argumente în funcția definită mai sus. Calculăm rezultatele." needs {#check-your-understanding}
  - Line 566: "Set the random seed" needs {#3-krylov-via-time-evolution}
  - Line 569: "how many random matrices will we make" needs {#31-time-evolution}
  - Line 628: "Choose the absolute error you can tolerate, and make a list for tracking the Krylov subspace size at which that error is achieved." needs {#32-how-to-implement-on-a-quantum-computer}
  - ... and 18 more
- **Image paths**: Count mismatch: EN=19, TR=6
- **Link URLs**: 15 URL difference(s)
  - Missing URL: /guides/error-mitigation-and-suppression-techniques#probabilistic-error-amplification-pea
  - Missing URL: /learning/images/courses/quantum-diagonalization-algorithms/krylov/extracted-outputs/410192fb-8197-4860-8c3a-2e874e2f9c56-0.avif
  - Missing URL: /learning/images/courses/quantum-diagonalization-algorithms/krylov/kqd-fig4.avif
  - Missing URL: /learning/images/courses/quantum-diagonalization-algorithms/krylov/kqd-fig5.avif
  - Missing URL: /learning/images/courses/quantum-diagonalization-algorithms/krylov/kqd-fig6.avif
  - ... and 10 more

### `learning/courses/quantum-machine-learning/data-encoding.mdx` — FAIL

- **Line count**: EN=1046, TR=517 (50.6% delta, max 15%)
- **Code blocks**: Count mismatch: EN=26, TR=25
- **LaTeX blocks ($$)**: EN=70, TR=8 (delta 62)
- **Inline LaTeX ($)**: EN=492, TR=92 (delta 400, max 35)
- **Indented headings**: 2 heading(s) with leading whitespace (breaks MDX)
  - Line 487: '# Getting the cx depths' has 4 leading space(s)
  - Line 493: '# Appending the cx gate counts to the lists. We shift the zz' has 4 leading space(s)
- **Heading count**: EN=24, TR=11
- **Heading anchors**: 4 anchor(s) missing
  - Line 472: "Initializing parameters and empty lists for depths" needs {#check-your-understanding}
  - Line 480: "Generating feature maps" needs {#amplitude-encoding}
  - Line 500: "Plot the output" needs {#check-your-understanding}
  - Line 508: "plt.suptitle('zz_feature_map(n)')" needs {#angle-encoding}
- **Image paths**: Count mismatch: EN=22, TR=0
- **Link URLs**: 37 URL difference(s)
  - Missing URL: /learning/images/courses/quantum-machine-learning/data-encoding/checkin2.avif
  - Missing URL: /learning/images/courses/quantum-machine-learning/data-encoding/checkin3.avif
  - Missing URL: /learning/images/courses/quantum-machine-learning/data-encoding/checkin4.avif
  - Missing URL: /learning/images/courses/quantum-machine-learning/data-encoding/checkin5.avif
  - Missing URL: /learning/images/courses/quantum-machine-learning/data-encoding/checkin6.avif
  - ... and 32 more

### `learning/courses/quantum-machine-learning/introduction.mdx` — FAIL

- **Line count**: EN=295, TR=6 (98.0% delta, max 15%)
- **Code blocks**: Count mismatch: EN=4, TR=0
- **Heading count**: EN=12, TR=0
- **Image paths**: Count mismatch: EN=2, TR=0
- **Frontmatter**: 1 issue(s)
  - Missing key: notebook_path
- **JSX tags**: 2 tag count mismatch(es)
  - IBMVideo: EN=1, TR=0
  - OpenInLabBanner: EN=1, TR=0
- **Link URLs**: 6 URL difference(s)
  - Missing URL: /learning/images/courses/quantum-machine-learning/introduction/qml-cr-background-2d-3d.avif
  - Missing URL: /learning/images/courses/quantum-machine-learning/introduction/qml-cr-background-sup-unsup.avif
  - Missing URL: https://arxiv.org/abs/1807.04271
  - Missing URL: https://epubs.siam.org/doi/10.1137/S0097539795293172
  - Missing URL: https://journals.aps.org/prresearch/abstract/10.1103/PhysRevResearch.6.023218
  - ... and 1 more

### `learning/courses/quantum-machine-learning/quantum-kernel-methods.mdx` — FAIL

- **Code blocks**: 1 block(s) differ
  - Block 20 (EN line 348, TR line 350): diff at line 7: EN='Saving to: ‘dataset_graph7.csv.15’' TR='Saving to: 'dataset_graph7.csv.15''
- **Link URLs**: 1 URL difference(s)
  - Missing URL: https://www.nature.com/articles/s41567-021-01287-z

### `learning/courses/quantum-safe-cryptography/asymmetric-key-cryptography.mdx` — FAIL

- **Line count**: EN=1571, TR=1 (99.9% delta, max 15%)
- **Code blocks**: Count mismatch: EN=50, TR=0
- **Inline LaTeX ($)**: EN=910, TR=0 (delta 910, max 35)
- **Heading count**: EN=41, TR=0
- **Image paths**: Count mismatch: EN=10, TR=0
- **Frontmatter**: 1 issue(s)
  - Missing key: notebook_path
- **JSX tags**: 3 tag count mismatch(es)
  - Admonition: EN=4, TR=0
  - DefinitionTooltip: EN=94, TR=0
  - OpenInLabBanner: EN=1, TR=0
- **Link URLs**: 46 URL difference(s)
  - Missing URL: /learning/courses/fundamentals-of-quantum-algorithms
  - Missing URL: /learning/images/courses/quantum-safe-cryptography/asymmetric-key-cryptography/ECCfig.avif
  - Missing URL: /learning/images/courses/quantum-safe-cryptography/asymmetric-key-cryptography/akc.avif
  - Missing URL: /learning/images/courses/quantum-safe-cryptography/asymmetric-key-cryptography/auth_key_exchange.avif
  - Missing URL: /learning/images/courses/quantum-safe-cryptography/asymmetric-key-cryptography/ca_akc.avif
  - ... and 41 more

### `learning/courses/quantum-safe-cryptography/quantum-safe-cryptography.mdx` — FAIL

- **Line count**: EN=520, TR=1 (99.8% delta, max 15%)
- **Code blocks**: Count mismatch: EN=15, TR=0
- **Inline LaTeX ($)**: EN=262, TR=0 (delta 262, max 35)
- **Heading count**: EN=22, TR=0
- **Image paths**: Count mismatch: EN=3, TR=0
- **Frontmatter**: 2 issue(s)
  - Missing key: notebook_path
  - Missing key: slug
- **JSX tags**: 3 tag count mismatch(es)
  - Admonition: EN=1, TR=0
  - DefinitionTooltip: EN=7, TR=0
  - OpenInLabBanner: EN=1, TR=0
- **Link URLs**: 45 URL difference(s)
  - Missing URL: /learning/images/courses/quantum-safe-cryptography/quantum-safe-cryptography/CVP.avif
  - Missing URL: /learning/images/courses/quantum-safe-cryptography/quantum-safe-cryptography/Lattice-reduction-wiki.avif
  - Missing URL: /learning/images/courses/quantum-safe-cryptography/quantum-safe-cryptography/SVP.avif
  - Missing URL: http://arxiv.org/abs/2208.08125
  - Missing URL: https://csrc.nist.gov/glossary/term/security_strength
  - ... and 40 more

### `learning/courses/variational-algorithm-design/examples-and-applications.mdx` — FAIL

- **Code blocks**: 69 block(s) differ
  - Block 17 (EN line 232, TR line 233): diff at line 7: EN='' TR='```'
  - Block 18 (EN line 250, TR line 243): diff at line 1: EN='```python' TR='```'
  - Block 19 (EN line 265, TR line 262): diff at line 1: EN='```python' TR='```'
  - Block 20 (EN line 272, TR line 271): diff at line 1: EN='```text' TR='```'
  - Block 21 (EN line 276, TR line 275): diff at line 1: EN='```python' TR='```'
  - ... and 64 more
- **LaTeX blocks ($$)**: EN=40, TR=6 (delta 34)
- **Inline LaTeX ($)**: EN=116, TR=6 (delta 110, max 35)
- **Indented headings**: 3 heading(s) with leading whitespace (breaks MDX)
  - Line 424: '#    entanglement="linear",' has 4 leading space(s)
  - Line 917: '#    cost = estimator.run(ansatz, hamiltonian, parameter_val' has 4 leading space(s)
  - Line 1285: '#    cost = estimator.run(ansatz, hamiltonian, parameter_val' has 4 leading space(s)
- **Heading count**: EN=17, TR=22
- **Heading anchors**: 13 anchor(s) missing
  - Line 796: "Or use a specific backend" needs {#change-the-initial-point}
  - Line 797: "backend = service.backend("ibm_brisbane")" needs {#experimenting-with-different-optimizers}
  - Line 818: "Estimated compute resource usage: 25 minutes. Benchmarked at 24 min, 30 sec on an Eagle r3 processor on 5-30-24" needs {#vqd-example}
  - Line 940: "SciPy minimizer routine" needs {#step-1-map-classical-inputs-to-a-quantum-problem}
  - Line 978: "x0 = np.zeros(ansatz.num_parameters)" needs {#change-betas}
  - ... and 8 more
- **Image paths**: Count mismatch: EN=10, TR=2
- **Link URLs**: 10 URL difference(s)
  - Missing URL: /learning/images/courses/variational-algorithm-design/examples-and-applications/extracted-outputs/13a4c371-fd40-4ce3-b737-268d4a4c9c2c-0.avif
  - Missing URL: /learning/images/courses/variational-algorithm-design/examples-and-applications/extracted-outputs/14e04c7a-e81f-41e1-b0cf-790954581be9-0.avif
  - Missing URL: /learning/images/courses/variational-algorithm-design/examples-and-applications/extracted-outputs/3eb71b79-a988-4807-aa88-7fb25a78a236-0.avif
  - Missing URL: /learning/images/courses/variational-algorithm-design/examples-and-applications/extracted-outputs/4238cc64-6910-43d2-889e-6322bf2864eb-0.avif
  - Missing URL: /learning/images/courses/variational-algorithm-design/examples-and-applications/extracted-outputs/686ee28e-9327-40d1-8d7c-3ec527160f01-0.avif
  - ... and 5 more

### `learning/modules/computer-science/quantum-key-distribution.mdx` — FAIL

- **Line count**: EN=1000, TR=1 (99.9% delta, max 15%)
- **Code blocks**: Count mismatch: EN=27, TR=0
- **Inline LaTeX ($)**: EN=318, TR=0 (delta 318, max 35)
- **Heading count**: EN=27, TR=0
- **Image paths**: Count mismatch: EN=1, TR=0
- **Frontmatter**: 1 issue(s)
  - Missing key: notebook_path
- **JSX tags**: 3 tag count mismatch(es)
  - Admonition: EN=1, TR=0
  - IBMVideo: EN=1, TR=0
  - OpenInLabBanner: EN=1, TR=0
- **Link URLs**: 10 URL difference(s)
  - Missing URL: /guides/cloud-setup
  - Missing URL: /guides/cloud-setup-untrusted
  - Missing URL: /guides/initialize-account
  - Missing URL: /guides/install-qiskit
  - Missing URL: /learning/images/modules/computer-science/quantum-key-distribution/extracted-outputs/2b538952-9e01-43a0-a1e6-a798683f93f0-1.avif
  - ... and 5 more
