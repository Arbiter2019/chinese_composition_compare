# Content Hash 接口方案

## Summary

当前项目为 FastAPI 单体后端，已有 `POST /api/composition_compare` 作文两两比对接口。新增 `POST /api/contentHash`，用于为单篇作文生成可复用的局部敏感 hash，支撑后续大批量、持续增长作文库的候选召回和相似度预筛。

本次只新增后端接口和后端 hash 能力，不新增前端页面。现有作文比对接口保持不变。

## 接口契约

请求路径：`POST /api/contentHash`

请求体：

```json
{
  "uuid": "request-001",
  "compositionContent": "作文内容",
  "language": "zh",
  "hashMethod": "MinHash",
  "para": 128
}
```

字段规则：

- `uuid`：必填字符串，标记唯一一次请求，响应中原样返回。
- `compositionContent`：必填非空字符串，待处理作文内容。
- `language`：可选，默认 `zh`；支持 `zh`、`en`。
- `hashMethod`：可选，默认 `MinHash`；支持 `MinHash`、`SimHash`，区分大小写。
- `para`：可选，默认 `128`；MinHash 时表示 permutations，SimHash 时表示 bit 数。

MinHash 响应：

```json
{
  "uuid": "request-001",
  "minhash": [123, 456],
  "parameter": 128
}
```

SimHash 响应：

```json
{
  "uuid": "request-001",
  "simhash": 12345678901234567890,
  "parameter": 128
}
```

### 请求参数 JSON Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "ContentHashRequest",
  "type": "object",
  "required": ["uuid", "compositionContent"],
  "properties": {
    "uuid": {
      "type": "string",
      "minLength": 1,
      "description": "标记唯一一次请求，响应中原样返回。"
    },
    "compositionContent": {
      "type": "string",
      "minLength": 1,
      "description": "待处理作文内容。"
    },
    "language": {
      "type": "string",
      "enum": ["zh", "en"],
      "default": "zh",
      "description": "作文语言。zh 使用 jieba 分词；en 按空白直接分词。"
    },
    "hashMethod": {
      "type": "string",
      "enum": ["MinHash", "SimHash"],
      "default": "MinHash",
      "description": "Hash 方法。缺省使用 MinHash。"
    },
    "para": {
      "type": "integer",
      "minimum": 1,
      "default": 128,
      "description": "Hash 参数。MinHash 表示 permutations；SimHash 表示 bit 数，且必须为 8 的倍数。"
    }
  },
  "additionalProperties": false
}
```

### 返回参数 JSON Schema

MinHash 响应：

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "ContentHashMinHashResponse",
  "type": "object",
  "required": ["uuid", "minhash", "parameter"],
  "properties": {
    "uuid": {
      "type": "string",
      "description": "来源于请求的 uuid。"
    },
    "minhash": {
      "type": "array",
      "items": {
        "type": "integer"
      },
      "description": "MinHash 签名数组，长度等于 parameter。"
    },
    "parameter": {
      "type": "integer",
      "minimum": 1,
      "description": "实际使用的 MinHash permutations 参数。"
    }
  },
  "additionalProperties": false
}
```

SimHash 响应：

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "ContentHashSimHashResponse",
  "type": "object",
  "required": ["uuid", "simhash", "parameter"],
  "properties": {
    "uuid": {
      "type": "string",
      "description": "来源于请求的 uuid。"
    },
    "simhash": {
      "type": "integer",
      "description": "SimHash 签名值，按 JSON number 返回。"
    },
    "parameter": {
      "type": "integer",
      "minimum": 1,
      "multipleOf": 8,
      "description": "实际使用的 SimHash bit 参数。"
    }
  },
  "additionalProperties": false
}
```

## 实现设计

- 新增 `config.py` 配置：`SHINGLE_N = 5`、`MINHASH_RANDOM_SEED = 42`、`DEFAULT_HASH_PARAMETER = 128`、`MINHASH_PRIME = 2147483647`。
- 中文 `zh` 使用 `jieba.cut` 分词后生成 shingle；英文 `en` 直接按空白分词后生成 shingle。
- Shingle 使用配置项 `SHINGLE_N`，当前为 token 级 5-gram；token 数不足时返回空 shingle 集合。
- MinHash 参考 notebook cell4：使用 `blake2b` 稳定 hash、素数模、固定随机种子生成置换参数；接口支持按 `para` 动态设置 permutations，并缓存置换参数。
- SimHash 参考 notebook cell4：使用 `blake2b` 生成指定位数 digest，按 bit 权重累加并返回 Python `int`。
- 空 shingle 策略沿用参考实现：MinHash 返回长度为 `para`、元素为 `MINHASH_PRIME` 的数组；SimHash 返回 `0`。

## 校验与错误

接口采用严格校验，以下情况返回 HTTP 400：

- 缺少或为空的 `uuid`。
- 缺少或为空的 `compositionContent`。
- `language` 不是 `zh` 或 `en`。
- `hashMethod` 不是 `MinHash` 或 `SimHash`。
- `para` 不是正整数。
- `hashMethod=SimHash` 时，`para` 不是 8 的倍数。

说明：SimHash 的 `para` 需要为 8 的倍数，因为当前实现通过 `blake2b(digest_size=para/8)` 生成位数组。

## 测试用例

- 中文文本调用 `jieba` 后生成 5-gram shingle。
- 英文文本按空白分词，不调用 `jieba`。
- token 数少于 `SHINGLE_N` 时 shingle 为空。
- 同一输入多次请求 hash 结果完全一致。
- MinHash 缺省参数返回长度为 128 的 `int` 数组。
- SimHash 缺省参数返回 JSON number。
- 调整 `para` 后，MinHash 返回数组长度随之变化，SimHash 计算位数随之变化。
- `hashMethod=SimHash` 时响应只包含 `simhash`，不包含 `minhash`。
- 缺少 `uuid`、缺少或为空的 `compositionContent`、非法枚举、非法 `para` 返回 400。
- 现有 `/api/composition_compare` 回归通过。
