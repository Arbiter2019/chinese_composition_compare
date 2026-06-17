# 作文查重系统 / Chinese Composition Plagiarism Detector

一个面向中文作文的句级查重工具，提供 Web 界面与命令行两种使用方式。  
A sentence-level plagiarism detection tool for Chinese essays, available as both a Web UI and CLI.

---

## 目录 / Table of Contents

1. [查重率计算规则 / How Similarity Is Calculated](#1-查重率计算规则--how-similarity-is-calculated)
2. [自定义阈值 / Customizing Thresholds](#2-自定义阈值--customizing-thresholds)
3. [前端界面使用方法 / Web UI Usage](#3-前端界面使用方法--web-ui-usage)
4. [CLI 使用方法 / CLI Usage](#4-cli-使用方法--cli-usage)
5. [部署指南 / Deployment](#5-部署指南--deployment)

---

## 1. 查重率计算规则 / How Similarity Is Calculated

### 1.1 句子切分 / Sentence Segmentation

核心函数位于 `ccpd.py` 的 `essay_overlap_analysis`。  
The core logic lives in `essay_overlap_analysis` in `ccpd.py`.

首先按中英文标点（`。！？；:：.!?;…`）将两篇文章各自切分为句子列表。  
Both essays are first split into sentence lists using Chinese/English punctuation (`。！？；:：.!?;…`).

### 1.2 三项指标 / Three Metrics

对"当前作文"中的**每一个句子** `s1`，在"目标作文"的所有句子中找到最相似的句子 `s2`，计算两项分值：

For **each sentence** `s1` in the source essay, the system finds the best-matching sentence `s2` in the target essay and computes two scores:

| 指标 / Metric | 算法 / Algorithm | 说明 / Description |
|---|---|---|
| **整句相似度** `sentence_score` | `difflib.SequenceMatcher` 字符级 ratio | 衡量两句字符序列的相似程度 / Character-sequence similarity |
| **词组相似度** `word_score` | Jaccard 系数（jieba 分词后的词集交并比）| 衡量词汇重叠程度 / Lexical overlap via jieba word sets |

$\mathrm{word\_score}(s_1, s_2)=\frac{|W_{s_1}\cap W_{s_2}|}{|W_{s_1}\cup W_{s_2}|}$

### 1.3 句子是否重复 / Sentence-Level Flag

当某句的 `sentence_score >= threshold`（默认 **0.85**）时，该句被标记为重复句（`is_repeated = True`）。

A sentence is flagged as repeated (`is_repeated = True`) when its `sentence_score >= threshold` (default **0.85**).

### 1.4 三项全局指标 / Three Article-Level Metrics

设当前作文切分出 ${N\_1}$ 句，目标作文切分出 $mathrm{N\_2}$ 句，被判定重复的句子数为 $R$：

Let $mathrm{N\_1}$ = sentences in source essay, $mathrm{N\_2}$ = sentences in target essay, $R$ = repeated sentence count:

| 返回字段 / Field | 公式 / Formula | 含义 / Meaning |
|---|---|---|
| `sentence_repeat_rate` | $R / mathrm{N\_1}$ | 当前作文中重复句比例 / Fraction of source sentences that are repeated |
| `symmetry_rate` | $2R / (mathrm{N\_1} + mathrm{N\_2})$ | 对称重复率，类似 F1，同时考虑两篇文章篇幅 / Symmetric rate balancing both essay lengths |
| `word_repeat_rate` | $\operatorname{mean}(\mathrm{all\ best\_word\_score})$ | 所有句子词组相似度的均值 / Mean lexical overlap across all sentences |

> **前端"文章重复率"展示的是 `symmetry_rate`**，因其对两篇文章的篇幅差异更具鲁棒性。  
> **The "文章重复率" shown in the Web UI is `symmetry_rate`**, as it is more robust to length differences between essays.

---

## 2. 自定义阈值 / Customizing Thresholds

### 2.1 句子判重阈值 / Sentence-Level Threshold

修改位置：`ccpd.py` → `essay_overlap_analysis` 函数签名的 `threshold` 参数（默认 `0.85`）。  
Location: the `threshold` parameter of `essay_overlap_analysis` in `ccpd.py` (default `0.85`).

```python
# ccpd.py
def essay_overlap_analysis(text1, text2, threshold=0.85):   # ← 修改此处 / change here
```

- **调高阈值**（如 `0.90`）：只有更高度相似的句子才算重复，查重更严格。  
  **Raise the threshold** (e.g. `0.90`): only highly similar sentences are flagged — stricter detection.
- **调低阈值**（如 `0.70`）：相似度稍低的句子也会被标为重复，查重更宽松。  
  **Lower the threshold** (e.g. `0.70`): moderately similar sentences are also flagged — looser detection.

如果通过 API 调用，可在 `main.py` 的 `composition_compare` 函数内将阈值作为参数传入：  
When called via API, you can pass a custom threshold inside `composition_compare` in `main.py`:

```python
# main.py（示例修改 / example change）
result = essay_overlap_analysis(original_text, candidate_text, threshold=0.80)
```

### 2.2 前端文章重复率颜色阈值 / Article-Level Color Thresholds (Frontend)

前端（`frontend/src/pages/Simulate.jsx`）通过颜色直观呈现"文章重复率"的风险等级，阈值写在渲染逻辑中：

The frontend (`frontend/src/pages/Simulate.jsx`) uses color coding to indicate risk levels for "文章重复率":

```jsx
// frontend/src/pages/Simulate.jsx
color: result.symmetry_rate >= 0.7   // ← 高风险红色阈值 / high-risk red threshold
    ? '#cf1322'
    : result.symmetry_rate >= 0.4    // ← 中风险橙色阈值 / medium-risk orange threshold
    ? '#d46b08'
    : '#3f8600'                      // ← 低风险绿色 / low-risk green
```

| 颜色 / Color | 条件 / Condition | 含义 / Meaning |
|---|---|---|
| 🔴 红色 Red | `symmetry_rate >= 0.70` | 高度重复 / High duplication |
| 🟠 橙色 Orange | `0.40 ≤ symmetry_rate < 0.70` | 中度重复 / Moderate duplication |
| 🟢 绿色 Green | `symmetry_rate < 0.40` | 基本原创 / Mostly original |

直接修改上述两个数字（`0.7` 和 `0.4`）即可调整颜色分界线，修改后需重新构建前端。  
Edit those two numbers (`0.7` and `0.4`) to change the color boundaries, then rebuild the frontend.

---

## 3. 前端界面使用方法 / Web UI Usage

启动服务后（见第 5 节），浏览器访问 `http://localhost:8540`，将自动跳转到查重页面。

After starting the server (see Section 5), open `http://localhost:8540` in your browser — it redirects to the comparison page automatically.

### 操作步骤 / Steps

1. **输入作文 / Enter Essays**  
   - 左侧文本框：粘贴"当前作文"（待查作文）。  
     Left box: paste the **source essay** (the one being checked).  
   - 右侧文本框：粘贴"目标作文"（用于对比的参考作文）。  
     Right box: paste the **target essay** (the reference to compare against).

2. **点击查重 / Click "查重"**  
   点击蓝色"查重"按钮提交，等待结果。  
   Click the blue **"查重"** button and wait for the result.

3. **查看结果 / View Results**  
   右侧弹出抽屉面板，显示三项汇总指标：  
   A drawer slides in from the right showing three summary metrics:

   | 指标 / Metric | 说明 / Description |
   |---|---|
   | **文章重复率** | `symmetry_rate`，颜色标红/橙/绿 |
   | **句子重复率** | `sentence_repeat_rate` |
   | **词组重复率** | `word_repeat_rate` |

   下方表格列出每个句子与目标作文的最佳匹配句、整句相似度及是否判定为重复。  
   The table below lists each sentence's best match, similarity score, and whether it was flagged.

4. **重置 / Reset**  
   点击"重置"按钮清空输入和结果。  
   Click **"重置"** to clear all inputs and results.

---

## 4. CLI 使用方法 / CLI Usage

### 4.1 直接运行内置示例 / Run the Built-in Demo

```bash
python ccpd.py
```

`ccpd.py` 底部的 `main()` 函数内置了一对示例作文，运行后会打印：  
The `main()` function at the bottom of `ccpd.py` contains a sample essay pair and prints:

```
句子颗粒度重复率: 0.xxxx
词组颗粒度的重复: 0.xxxx
对称相似度: 0.xxxx
{'sentence': '...', 'best_match': '...', 'sentence_score': ..., 'word_score': ..., 'is_repeated': ...}
...
```

### 4.2 在代码中调用 / Call from Your Own Script

```python
from ccpd import essay_overlap_analysis

text1 = "你的第一篇作文内容..."
text2 = "你的第二篇作文内容..."

result = essay_overlap_analysis(text1, text2, threshold=0.85)

print(f"文章重复率 (symmetry):   {result['symmetry_rate']:.2%}")
print(f"句子重复率:              {result['sentence_repeat_rate']:.2%}")
print(f"词组重复率:              {result['word_repeat_rate']:.2%}")

for detail in result["details"]:
    if detail["is_repeated"]:
        print(f"[重复] {detail['sentence'][:30]}... → 相似度 {detail['sentence_score']:.2%}")
```

### 4.3 通过 HTTP API 调用 / Call via HTTP API

服务启动后，可用任意 HTTP 客户端调用：  
Once the server is running, call it with any HTTP client:

#### 4.3.1 作文查重 / Composition Compare

```bash
curl -X POST http://localhost:8540/api/composition_compare \
  -H "Content-Type: application/json" \
  -d '{
    "original_text": "第一篇作文...",
    "candidate_text": "第二篇作文..."
  }'
```

**响应示例 / Response example:**

```json
{
  "symmetry_rate": 0.8571,
  "sentence_repeat_rate": 0.9000,
  "word_repeat_rate": 0.7234,
  "details": [
    {
      "sentence": "热烈的掌声响起",
      "best_match": "热烈的掌声响起",
      "sentence_score": 1.0,
      "word_score": 1.0,
      "is_repeated": true
    }
  ]
}
```

#### 4.3.2 内容指纹 / Content Hash

`POST /api/contentHash` 用于对作文内容生成稳定的内容指纹，支持 `MinHash` 和 `SimHash` 两种算法。  
`POST /api/contentHash` generates a stable content fingerprint for composition text, supporting both `MinHash` and `SimHash`.

**请求参数 / Request fields:**

| 字段 / Field | 类型 / Type | 必填 / Required | 默认值 / Default | 说明 / Description |
|---|---|---:|---|---|
| `uuid` | string | 是 / Yes | - | 业务侧传入的作文或请求唯一标识，响应会原样返回 / Caller-provided unique id, echoed in the response |
| `compositionContent` | string | 是 / Yes | - | 需要生成指纹的作文正文 / Composition text to hash |
| `language` | string | 否 / No | `zh` | 文本语言，仅支持 `zh` 或 `en` / Text language, only `zh` or `en` |
| `hashMethod` | string | 否 / No | `MinHash` | 指纹算法，仅支持 `MinHash` 或 `SimHash` / Hash algorithm, only `MinHash` or `SimHash` |
| `para` | integer | 否 / No | `128` | 算法参数：`MinHash` 表示签名长度；`SimHash` 表示 bit 位数，且必须是 8 的倍数 / Algorithm parameter: signature length for `MinHash`; bit width for `SimHash`, which must be a multiple of 8 |

参数校验 / Validation:

- `uuid` 不能为空 / `uuid` must not be empty.
- `compositionContent` 不能为空 / `compositionContent` must not be empty.
- `language` 仅支持 `zh`、`en` / `language` only supports `zh` or `en`.
- `hashMethod` 仅支持 `MinHash`、`SimHash` / `hashMethod` only supports `MinHash` or `SimHash`.
- `para` 必须为正整数 / `para` must be a positive integer.
- 当 `hashMethod` 为 `SimHash` 时，`para` 必须是 8 的倍数 / For `SimHash`, `para` must be a multiple of 8.

**MinHash 请求示例 / MinHash request example:**

```bash
curl -X POST http://localhost:8540/api/contentHash \
  -H "Content-Type: application/json" \
  -d '{
    "uuid": "essay-001",
    "compositionContent": "今天天气很好，我们一起去公园散步。",
    "language": "zh",
    "hashMethod": "MinHash",
    "para": 128
  }'
```

**MinHash 响应示例 / MinHash response example:**

```json
{
  "uuid": "essay-001",
  "minhash": [1947842, 7308921, 42177635],
  "parameter": 128
}
```

`minhash` 实际会返回 `para` 个整数；上例仅展示部分字段值。  
The actual `minhash` array contains `para` integers; the example above is shortened.

**SimHash 请求示例 / SimHash request example:**

```bash
curl -X POST http://localhost:8540/api/contentHash \
  -H "Content-Type: application/json" \
  -d '{
    "uuid": "essay-002",
    "compositionContent": "The weather is nice today, so we walked in the park.",
    "language": "en",
    "hashMethod": "SimHash",
    "para": 64
  }'
```

**SimHash 响应示例 / SimHash response example:**

```json
{
  "uuid": "essay-002",
  "simhash": 13701087659101639211,
  "parameter": 64
}
```

生成逻辑 / Generation logic:

- 中文文本使用 `jieba` 分词；英文文本按空格切分 / Chinese text is tokenized with `jieba`; English text is split by spaces.
- 分词后按 `SHINGLE_N = 5` 生成 token shingles / Tokens are converted into shingles with `SHINGLE_N = 5`.
- `MinHash` 使用固定随机种子生成可复现签名 / `MinHash` uses a fixed random seed for reproducible signatures.
- `SimHash` 返回一个整数形式的 bit 签名 / `SimHash` returns the bit signature as an integer.

在线接口文档（Swagger UI）可访问：`http://localhost:8540/docs`  
Interactive API docs (Swagger UI) are available at: `http://localhost:8540/docs`

---

## 5. 部署指南 / Deployment

### 5.1 环境要求 / Requirements

- Python ≥ 3.9  
- Node.js ≥ 18（仅构建前端时需要 / only needed to build the frontend）

### 5.2 安装依赖 / Install Dependencies

```bash
# Python 依赖 / Python dependencies
pip install -r requirements.txt
```

`requirements.txt` 包含 / contains:

```
fastapi>=0.110.0
uvicorn[standard]>=0.29.0
numpy>=1.24.0
jieba>=0.42.1
```

### 5.3 仅启动后端（无前端）/ Backend Only

```bash
python main.py
```

服务监听 `http://0.0.0.0:8540`，仅提供 API，无页面。  
The server listens on `http://0.0.0.0:8540` and serves the API only (no UI).

### 5.4 完整部署（前端 + 后端）/ Full Stack Deployment

**第一步：构建前端 / Step 1 — Build the frontend**

```bash
cd frontend
npm install
npm run build
cd ..
```

构建产物输出到 `frontend/dist/`，FastAPI 会自动托管此目录。  
Build output goes to `frontend/dist/`, which FastAPI serves automatically.

**第二步：启动服务 / Step 2 — Start the server**

```bash
python main.py
```

访问 `http://localhost:8540` 即可使用完整的 Web 界面。  
Visit `http://localhost:8540` to use the full Web UI.

### 5.5 生产环境部署 / Production Deployment

推荐使用进程管理器（如 `systemd` 或 `supervisor`）托管服务，并在前面挂 Nginx 反向代理：  
Use a process manager (e.g. `systemd` or `supervisor`) and put Nginx in front as a reverse proxy:

```nginx
# Nginx 示例配置 / Example Nginx config
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8540;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

若需修改监听端口，编辑 `main.py` 末尾的 `uvicorn.run` 调用：  
To change the port, edit the `uvicorn.run` call at the bottom of `main.py`:

```python
uvicorn.run("main:app", host="0.0.0.0", port=8540, reload=False)
#                                                   ^^^^ 修改此处 / change here
```

### 5.6 开发模式 / Development Mode

前后端分离开发时，Vite 提供了代理配置（`frontend/vite.config.js`），前端热重载：  
For frontend-only development with hot reload, Vite proxies API requests to the backend:

```bash
# 终端 1：启动后端 / Terminal 1: start backend
python main.py

# 终端 2：启动前端开发服务器 / Terminal 2: start frontend dev server
cd frontend
npm run dev
```

前端默认运行在 `http://localhost:5173`，API 请求自动代理到后端。  
The frontend runs at `http://localhost:5173` and proxies API calls to the backend automatically.
