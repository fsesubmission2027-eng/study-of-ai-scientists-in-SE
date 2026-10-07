# Seeds for ICSE-2025-010 — Verification of Heterogeneous Programs with Missing Source Code

> 论文正式标题：**Hetrify: Efficient Verification of Heterogeneous Programs on RISC-V**（ICSE 2025 Distinguished Paper）。

## 下载数据（主机侧）

```bash
chmod +x download_hetrify_svcomp.sh
./download_hetrify_svcomp.sh
# 仅工具：           FETCH_MODE=tools ./download_hetrify_svcomp.sh
# 仅 SV-COMP 2024：  FETCH_MODE=svcomp24 ./download_hetrify_svcomp.sh
# 2024+2023+CBMC：   FETCH_MODE=both ./download_hetrify_svcomp.sh
# 含 Ghidra：        FETCH_MODE=all ./download_hetrify_svcomp.sh
# 只下不解压：       EXTRACT=0 ./download_hetrify_svcomp.sh
```

| 项 | 值 |
|----|-----|
| 主机路径 | `~/ai_scientist_inputs/shared_datasets/hetrify-svcomp` |
| Docker 挂载 | `/shared/hetrify-svcomp`（只读） |
| Agent 路径 | `dataset_candidate/hetrify-svcomp/` |
| 环境变量 | `HETRIFY_SVCOMP_HOME`, `SVCOMP24_HOME`, `SVCOMP23_HOME`, `CBMC_DEB` |

### 体积（API / Zenodo 已核对）

| 资源 | 来源 | 体积 |
|------|------|------|
| SV-COMP 2024 benchmarks zip | https://doi.org/10.5281/zenodo.10669723 | **1,756,960,125 B ≈ 1.76 GiB**（Zenodo 标 ~1.8 GB） |
| SV-COMP 2023 benchmarks zip | https://doi.org/10.5281/zenodo.7627783 | **1,396,566,648 B ≈ 1.40 GiB** |
| CBMC 5.95.1（Ubuntu 22.04 deb） | GitHub `diffblue/cbmc` | **~67.4 MB** |
| Ghidra 12.1.3 PUBLIC（可选 RQ3） | GitHub NSA/ghidra | **~569 MiB** 压缩包 |
| RISC-V GCC | Ubuntu `gcc-riscv64-unknown-elf` | 容器内 apt 安装（不进 shared zip） |
| IDA Pro | Hex-Rays | **商业软件，不下载** |
| 论文工具 Hetrify | https://anonymous.4open.science/r/Hetrify | 体积未知；匿名仓可能过期 |

默认 `FETCH_MODE=benchmarks+tools` ≈ **1.76 GiB + 67 MB**；解压后磁盘通常再占 **2–3+ GiB**。  
若还要 RQ2 大程序池：`FETCH_MODE=both` 再加约 **1.4 GiB**。

### 论文评测集（从 SV-COMP 构造，无单独发布包）

| 集合 | 规模 | 做法 |
|------|------|------|
| RISC-V 汇编程序 | 100（50 正确 / 50 错误） | SV-COMP 2024，1–3 个函数 → `riscv64-unknown-elf-gcc` 出汇编 |
| 大规模异构（缺函数源码） | 30（15/15） | SV-COMP 2024+2023，>5 函数、>300 LOC → 关键函数打成 RISC-V `.a` |
| RISC-V 二进制 | 100 | 由汇编集再链接，供 Ghidra/IDA 对比 |

## Docker / 容器环境

`task.env` + `seeds/container_setup.sh` 在容器启动时安装：

- **CBMC 5.95.x**（从挂载的 `.deb` 安装；与论文 5.95 对齐）
- **`gcc-riscv64-unknown-elf`** + binutils（论文同名工具链）
- **OpenJDK 17**（可选 Ghidra headless）
- Python venv：`/opt/icse-2025-010-venv`

| 参数 | 论文设置 | `task.env` |
|------|----------|------------|
| 内存 | 384 GB | `MEMORY=64g`（远低于论文；需缩减协议并披露） |
| CPU | dual EPYC 7713 | `CPUS=8` |
| 超时 | 3000 s / 程序 | 见 `benchmark_config.json` |
| unwind（正确程序） | 20 | 同上 |

**注意**：完整 130 任务 × 3000s 可达 **>80 CPU-hour**；沙盒建议先用小子集 + 更短超时，并在结果中写明 reduced protocol。

## 启动 benchmark

```bash
./download_hetrify_svcomp.sh          # 主机执行一次（建议先 benchmarks+tools）
./run_aiscientist_benchmark.sh run    # 或 run_airesearcher_benchmark.sh
```

## 评估协议（默认）

- Backend：**CBMC**；正确程序 unwind=20；错误程序不固定 unwind；超时 3000s（可降配）
- 指标：**Correctness Rate**、**Error Rate**
- Baseline：缺函数时直接 CBMC（stubs）；RQ3 用 Ghidra（若已下）；跳过 IDA 并说明
- Hetrify 工具不可用时：按论文方法自实现 RISC-V→C 转换 + CBMC，勿用假数据冒充 SV-COMP
