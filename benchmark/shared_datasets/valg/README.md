# Valg: Runtime Verification with Feedback-Guided Selective Monitoring
Valg is the first RV technique that performs on-the-fly selective monitoring. It is also the first reinforcement learning (RL)-based technique to speed up RV. For more details, please refer to the paper. Appendix can be found [here](appendix.pdf).

This repository contains the source code of Valg, and scripts and data for the paper.

### Evaluation Subjects
You can find the list of projects used for evaluation [here](data/projects.csv). Also, the revisions (shas) used for evaluation can be found [here](data/shas/).

## Structure
- `data/`: evaluation results
- `experiments/`: scripts and other tools (`*.jar`) used for evaluation
- `javamop/`: base source code of JavaMOP and TraceMOP
- `logicrepository/` `plugins_logicrepository/`: source code for properties in specifications
- `rv-monitor-rt/` `rv-monitor/`: source code for RV classes
- `scripts/`: main scripts to run Valg

## How to Use

### Prerequisite

Valg supports Docker environment. Please make sure Docker is installed. For commands that run inside a Docker container, we use `$'` notation.

### How to Setup and Run
1. First, clone the repository, and build and run the Docker image:<br />
`$ git clone https://github.com/Amazing-Spots/Valg.git && cd Valg`<br />
`$ docker build -f scripts/Dockerfile . -t valg`<br />
`$ docker run -it valg /bin/bash` 
 
2. Then, inside the image, build Valg agents: `$' bash setup.sh` 

3. Once completed, detach from the container (`ctrl + p` then `ctrl + q`) and commit to a new image:<br />
 `$ docker ps` (check the container ID)<br />
 `$ docker commit [CONTAINER ID] valg:latest`
 
4. Then, attach to the container again, and change directory:<br />
 `$ docker container attach [CONTAINER ID]`<br /> 
 `$' cd Valg/scripts/`
 
5. Now, you can easily run ValgJ and ValgT with the scripts provided:<br />
`$' bash not_collect_traces.sh [REPO] [SHA] [OUTPUT]` (for ValgJ)<br />
`$' bash collect_traces.sh [REPO] [SHA] [OUTPUT]` (for ValgT)<br />

For example, the following runs are possible:<br />
`$' bash not_collect_traces.sh dperezcabrera/jpoker e771da71c3c5dc25b99355e41491933e78732e3e output-jpoker-valgj`<br />
`$' bash collect_traces.sh almson/almson-refcount ded7fe38d1e84f2af98f1d845d30fcc46aad197b output-almson-refcount-valgt`

After runs, violations can be found in `[OUTPUT]/project/violation-counts` (ValgJ), and traces can be found in `[OUTPUT]/all-traces/unique-traces.txt` (ValgT).<br />

To run for all projects, detach from the container and run `$ bash experiments/run_tool.sh` from the host.

### How to Change Hyperparameters
Valg currently provides four types of parameters: learning rate, epsilon, threshold, and (two) initial values. The default values are 0.9 (learning rate), 0.1 (epsilon), 1e-5 (threshold), and 5 and 0 (initial values). One can easily rebuild the agent with different hyperparameter values: `$' bash install.sh [LEARNING RATE] [EPSILON] [THRESHOLD] [INIT-CREATE] [INIT-NCREATE]`<br />

For example, the following configurations are possible:<br />
`$' bash install.sh true false 0.95 0.2`<br />
`$' bash install.sh false false 0.85 0.3 0.001`<br />

During build, these logs will be observed:<br />
- `Flags for rv-monitor:  -locationFromAjc -alpha 0.95 -epsilon 0.2 -threshold 0.0001 -initc 5.0 -initn 0.0`<br />
- `Flags for rv-monitor:  -locationFromAjc -alpha 0.85 -epsilon 0.3 -threshold 0.001 -initc 5.0 -initn 0.0`

## Comparison with Other Tools
This repository provides six tools to compare with Valg: JavaMOP, TraceMOP, RS10{J,T}, and RS50{J,T} (random sampling with 10% and 50%, respectively). The tools can be found in `experiments/` directory.<br />

To try out another tool, simply replace `no-track-no-stats-agent.jar` or `track-no-stats-agent.jar`:<br />
- For JavaMOP-based variants: `$' cp ../experiments/{javamop, rs10j, rs50j}.jar no-track-no-stats-agent.jar`<br />
- For TraceMOP-based variants: `$' cp ../experiments/{tracemop, rs10t, rs50t}.jar track-no-stats-agent.jar`<br />

### Evaluation
We conduct four runs for ValgJ, ValgT vs JavaMOP, TraceMOP:

`$' bash not_collect_traces.sh dperezcabrera/jpoker e771da71c3c5dc25b99355e41491933e78732e3e output-jpoker-valgj`
```
[OK] Cloning project dperezcabrera/jpoker
[OK] Running MOP
[OK] Duration: 62303 ms
```
`$' bash not_collect_traces.sh dperezcabrera/jpoker e771da71c3c5dc25b99355e41491933e78732e3e output-jpoker-javamop`
```
[OK] Cloning project dperezcabrera/jpoker
[OK] Running MOP
[OK] Duration: 130549 ms
```
`$' bash collect_traces.sh almson/almson-refcount ded7fe38d1e84f2af98f1d845d30fcc46aad197b output-almson-refcount-valgt`
```
[OK] Cloning project almson/almson-refcount
[OK] Collecting traces
[OK] Duration: 21618 ms
```
`$' bash collect_traces.sh almson/almson-refcount ded7fe38d1e84f2af98f1d845d30fcc46aad197b output-almson-refcount-tracemop`
```
[OK] Cloning project almson/almson-refcount
[OK] Collecting traces
[OK] Duration: 70617 ms
```
The results show that Valg brings much speedup. Also, it preserves all of 6 violations (`jpoker`) and 27 unique traces (`almson-refcount`) that
JavaMOP and TraceMOP check.

## Hyperparameter Tuning
Hyperparameters of Valg can be automatically tuned using Optuna. Copy the tuning script `$' cp ../experiments/tuning.py .` and run the following command: `$' python3 tuning.py [REPO] [SHA]`. The current script is configured to run 100 trials.<br />

For example, when `$' python3 tuning.py agarciadom/xeger f3b8a33b0f4438d639150b57b9a0257d50c71bc2`, the output looks like the following:
```
[I 2025-05-30 15:20:08,698] A new study created in RDB with name: xeger-study
[I 2025-05-30 15:22:57,939] Trial 0 finished with value: 1669.0 and parameters: {'alpha': 0.5800000000000001, 'epsilon': 0.9600000000000001}. Best is trial 0 with value: 1669.0.
[I 2025-05-30 15:25:34,232] Trial 1 finished with value: 1638.0 and parameters: {'alpha': 0.06999999999999999, 'epsilon': 0.46}. Best is trial 0 with value: 1669.0.
...
```
