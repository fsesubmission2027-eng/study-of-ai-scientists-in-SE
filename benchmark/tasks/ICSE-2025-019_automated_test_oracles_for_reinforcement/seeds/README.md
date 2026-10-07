# Seeds for ICSE-2025-019 — LPEA Oracle (RL Software Test Oracle)

> 论文正式标题：**A Test Oracle for Reinforcement Learning Software based on Lyapunov Stability Control Theory**（ICSE 2025）。

## 下载数据（主机侧）

```bash
chmod +x download_lpea_oracle.sh
./download_lpea_oracle.sh
# 可选：从 GitHub clone
# FETCH_MODE=git ./download_lpea_oracle.sh
```

| 项 | 值 |
|----|-----|
| 主机路径 | `~/ai_scientist_inputs/shared_datasets/lpea-oracle-icse2025` |
| Docker 挂载 | `/shared/lpea-oracle-icse2025`（只读） |
| Agent 路径 | `dataset_candidate/lpea-oracle-icse2025/` |
| 环境变量 | `LPEA_ORACLE_HOME`, `LPEA_REPO_HOME`, `LPEA_TESTING_HOME`, `LPEA_BUG_LIB_HOME` |
| Zenodo | https://doi.org/10.5281/zenodo.14759447 |
| GitHub | https://github.com/QixinWangCpsLab/LPEA_Oracle_ICSE2025_AE_Track |

### 体积

Zenodo zip **约 4.3 MiB**。解压后主要是 SB3 fork + LPEA 脚本（通常几十 MB 级，见 `.artifact_meta.txt` / `du -sh`）。**没有 GB 级外部语料**；benchmark 由 SB3 + bug injection 构造。

## Docker / 容器环境

`task.env` + `seeds/container_setup.sh`：

- **Python venv**：`/opt/icse-2025-019-venv`
- **CPU PyTorch 2.4** + Gymnasium / SciPy / cvxpy / control / openpyxl
- **Editable SB3**：从 artifact 拷到 `/opt/icse-2025-019-sb3` 再 `pip install -e .`

| 参数 | 论文设置 | `task.env` |
|------|----------|------------|
| 计算 | Ryzen 7 + RTX 3060，LPEA ≤129h | `MEMORY=32g`, `CPUS=8`, CPU torch |
| GPU | 论文使用 Laptop GPU | `REQUIRES_GPU=false`（需要时可在 project/ 装 CUDA torch） |

## 启动 benchmark

```bash
./download_lpea_oracle.sh
./run_aiscientist_benchmark.sh run
# 或 ./run_airesearcher_benchmark.sh run
```
