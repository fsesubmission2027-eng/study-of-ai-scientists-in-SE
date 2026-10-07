# Seeds for ICSE-2025-008 — Early Detection of System Performance Regressions

> 论文正式标题：**Early Detection of Performance Regressions by Bridging Local Performance Data and Architectural Models**（ICSE 2025 Distinguished Paper）。

## 下载数据（主机侧）

```bash
chmod +x download_perf_regression_subjects.sh
./download_perf_regression_subjects.sh
# 只要源码：     FETCH_MODE=subjects ./download_perf_regression_subjects.sh
# 含 Zenodo：    FETCH_MODE=all ./download_perf_regression_subjects.sh
# 预拉 TeaStore 镜像（约 2.2 GiB）：PULL_IMAGES=1 ./download_perf_regression_subjects.sh
```

| 项 | 值 |
|----|-----|
| 主机路径 | `~/ai_scientist_inputs/shared_datasets/perf-regression-early-detect` |
| Docker 挂载 | `/shared/perf-regression-early-detect`（只读） |
| Agent 路径 | `dataset_candidate/perf-regression-early-detect/` |
| 环境变量 | `PERF_REGRESSION_EARLY_DETECT_HOME`, `TEASTORE_HOME`, `TRAINTICKET_HOME`, `JMETER_HOME` |

### 体积（已核对 / 估算）

| 资源 | 来源 | 体积 |
|------|------|------|
| TeaStore 源码仓库 | https://github.com/DescartesResearch/TeaStore | GitHub `size` ≈ **105 MiB**（107367 KiB）；浅克隆更小 |
| TrainTicket 源码仓库 | https://github.com/FudanSELab/train-ticket | GitHub `size` ≈ **81 MiB**（82675 KiB）；浅克隆更小 |
| Apache JMeter 5.6.3 | archive.apache.org | **~83 MiB**（87,414,762 B）压缩包 |
| TeaStore Docker 镜像（7 个 latest） | Docker Hub `descartesresearch/teastore-*` | 合计约 **2.2 GiB** 镜像层 |
| TrainTicket 运行时 | 上游 wiki | docker-compose：**≥24 GiB RAM、≥50 GiB 磁盘** |
| Zenodo 复现包 | https://doi.org/10.5281/zenodo.13135986 | 含 QPN 模型/脚本/结果；本机若 API 不通需手动下载到 `replication/` |

说明：论文实验用 **Podman 4.6.2 + podman-compose 1.0.6**；沙盒里装 Docker CLI/Compose 作为等价编排工具。

### 复现包内容（Zenodo）

论文脚注：evaluation setup、scripts、results 与 architectural models（QPN）均在 Zenodo。若 `FETCH_MODE=all` 时 API 超时，请浏览器打开 DOI，把文件放到：

`shared_datasets/perf-regression-early-detect/replication/`

## Docker / 容器环境

`task.env` + `seeds/container_setup.sh` 在容器启动时安装：

- **OpenJDK 17**（`java` / `javac`）
- **Maven**（构建 TeaStore / TrainTicket）
- **Docker CLI + Compose v2**（部署微服务；论文用 Podman）
- Python venv：`/opt/icse-2025-008-venv`（numpy/pandas/scipy/statsmodels，用于 Cliff’s Delta / Wilcoxon 等）

| 参数 | 论文设置 | `task.env` |
|------|----------|------------|
| 内存 | 2×32 GB 机器 | `MEMORY=40g`（TrainTicket wiki 要求 ≥24G） |
| CPU | i7-6700 | `CPUS=8` |
| 组件测试 | 每测 30 次 | 见 `benchmark_config.json` |
| 系统测试 | 15 min × 3，丢弃前 5 min | 同上 |

**嵌套容器注意**：ResearchClaw 默认挂载 host `docker.sock`；AI-Scientist / AI-Researcher 默认不挂 sock。无 daemon 时优先做 **组件级 unit-test 性能数据 + 架构模型传播预测**；系统级 load test 作为 oracle，需主机 Docker/Podman。

## 启动 benchmark

```bash
./download_perf_regression_subjects.sh   # 主机执行一次
./run_aiscientist_benchmark.sh run       # 或 run_airesearcher_benchmark.sh
```

## 评估协议（默认）

- 对象：**TeaStore**（~33k LOC, 163 unit tests）与 **TrainTicket**（~289k LOC, 628 unit tests）
- 回归注入：busy-wait，位置 L1/L2/L3 × 强度 Low/Medium/High（10% / 50% / 250%）
- 指标：response time MPD / Cliff’s Delta、CPU MPD、TP/TN/FP/FN（相对系统级 oracle）
- 约束：对新版本的**预测**不得使用系统级测试数据；系统级测试仅作 ground truth
