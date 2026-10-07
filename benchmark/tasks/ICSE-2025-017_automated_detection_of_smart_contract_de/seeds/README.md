# Seeds for ICSE-2025-017 — TON Smart Contract Defect Detection

> 论文正式标题：**Enhancing The Open Network: Definition and Automated Detection of Smart Contract Defects**（ICSE 2025 Distinguished Paper / TONScanner）。

## 下载数据（主机侧）

```bash
chmod +x download_ton_contracts.sh
./download_ton_contracts.sh
# 可选：一并保留 TONScanner 二进制
# FETCH_MODE=all ./download_ton_contracts.sh
```

| 项 | 值 |
|----|-----|
| 主机路径 | `~/ai_scientist_inputs/shared_datasets/ton-smart-contract-defects` |
| Docker 挂载 | `/shared/ton-smart-contract-defects`（只读） |
| Agent 路径 | `dataset_candidate/ton-smart-contract-defects/` |
| 环境变量 | `TON_DEFECTS_HOME`, `TON_CONTRACTS_HOME`, `TON_REPO_HOME`, `TON_SAMPLES_HOME` |
| Artifact | https://anonymous.4open.science/r/TON_support_material-ECD4/ |

### 体积

完整 zip 从 anonymous.4open 拉取（约 19k 文件）。下载完成后看 `.artifact_meta.txt` / `du -sh`。论文评测集：**922 FunC + 718 Tact ≈ 1640** 合约（源码级，通常远小于 GB 级二进制语料）。

默认 `FETCH_MODE=datasets` **不强制**需要 TONScanner ELF；`FETCH_MODE=all` 时额外保留 `tools/TONScanner` + `lib64`（合计约数 MiB）。

## Docker / 容器环境

`task.env` + `seeds/container_setup.sh`：

- **GCC / G++ / CMake / Ninja**
- **Python venv**：`/opt/icse-2025-017-venv`
- **Node/npm**（可选，便于拉取 Tact 编译器）

| 参数 | 论文设置 | `task.env` |
|------|----------|------------|
| 内存 | 120 GB | `MEMORY=32g` |
| CPU | 12 核 | `CPUS=8` |

## 启动 benchmark

```bash
./download_ton_contracts.sh
./run_aiscientist_benchmark.sh run
# 或 ./run_airesearcher_benchmark.sh run
```
