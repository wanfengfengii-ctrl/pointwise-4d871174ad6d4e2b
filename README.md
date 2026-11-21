# 台架记录室 V1

台架日志记录的是各原行的调整量和出处。记录室保留每次录入的全量修订，值班工程师冻结指定版次后回放整卷。交班员把异常闭窗交给隔离机，夜班可以关闭站端后按实际实收号复核，次班按报告号领取当时的读数和出处。

## 运行

使用 Python 3.11 标准库和 SQLite。在项目根目录运行完整回归和演示。

```text
python3 -B check_project.py
python3 -B demo.py
```

演示在临时目录内显式导入 `samples/shift.json`，用独立的站端和隔离库运行录卷、冻结、整卷参照、窗口发行、实收、断源复核、更正及重开复领。需初始化自己的两个库时，运行 `python3 -B init_project.py station.sqlite isolation.sqlite`。重复初始化保留现有记录，初始化不会导入样例。以下 Python API 接受相应的已初始化连接，各写入入口拥有自己的事务。

## 业务接口

| 导入路径 | 调用 | 成功结果 |
| --- | --- | --- |
| `source.store` / `receipt.storage` | `open_source_db(path)` / `open_isolation_db(path)` | 站端或隔离连接，由调用者关闭 |
| `source.intake` | `record(db, roll_id, rows, parent_revision_id=None)` | 已接纳的修订号 |
| `source.revisions` | `current_revision(db, roll_id)` / `load_revision(db, revision_id)` | 当前修订或按号读取的修订快照 |
| `source.freeze` | `freeze(db, roll_id, revision_id)` | 固定卷号，同一修订重复冻结返回原号 |
| `replay.readings` | `replay(db, frozen_id, initial_value)` | 包含冻结身份及原序 `Reading` 的 `ReplayTrace` |
| `issue.registry` | `issue(db, frozen_id, windows)` / `get_issued_package(db, issuance_id)` | 含 `issuance_id` 和完整 `packet` 字节的发行件 |
| `receipt.intake` | `receive(db, packet)` | 实际验收的固定实收号 |
| `receipt.storage` | `load_receipt(db, receipt_id)` | 实收身份、实际原件字节和已验正文 |
| `review.requests` | `review(db, receipt_id, initial_value)` | 已提交的 `StoredReport`，含报告号、初值、实收号、发行号、冻结身份和原序明细 |
| `review.history` | `get(db, report_id)` | 原定稿，读持久明细 |

`rows` 是按实际录制顺序给出的 `SourceRow` 或具有 `row_no`、`delta`、`origin` 三个字段的映射序列。行号是唯一正整数，可有缺口，原序由录入次序决定。出处是非空的原日志定位文本。更正提交完整的替代序列，父修订须属于指定卷；省略父修订时以写事务所见的当前版为父。更正保留旧修订及其冻结引用。空序列是合法空卷。

数值以同一台架量程刻度计。接受 `int`、`Fraction` 及整数、分数或有限小数字符串，存档使用约分字符串。浮点、布尔和空值均拒绝，初值必须在闭区间 `[0,10]`。每步计算 `min(10, max(0, s + delta))`，结果既是该行读数，也是下一行输入。给定冻结版和初值，回放的读数与顺序固定。

`windows` 是一个或两个闭行号区间，每个区间为 `(first, last)` 或 `ClosedWindow`，均须选中原行。端点共享算重叠。窗口请求顺序不影响交付顺序。窗口件仅包含所选原行、原序位、出处及离线复核所需的派生依据，未选原行及逐条原始增量留在站端。派生依据是每个间隙（窗前、窗间及窗内省略行）逐行夹紧后的复合变换 `shift low high`：对输入 `s` 取 `min(high, max(low, s + shift))`，精确等价于把该段原行逐条相加并逐条夹到 `[0,10]`，因此复核只需沿原序一次起算、连续携带状态。V1 传输外层用 UTF-8 JSON 表示，含 `version`、`issuance_id`、`body`、`sha256`，其中 `body` 是实际 UTF-8 正文的 Base64 编码，校验绑定发行身份与实际正文字节。实收入库保留完整投递字节，原样重送返回原实收号，同一发行身份的异件拒绝。传输校验用于检测损坏。

不合法输入、窗口、包或发行身份冲突抛出 `ValueError`。对合法编号找不到相应对象时抛出 `LookupError`。SQLite 错误原样返回。失败的更正、发行和实收无新增，失败的签存回滚报告头与所有明细。报告只在事务提交后返回。更正与重开后，历史入口仍按原报告号领取原初值、原实收身份、冻结修订和原序读数及出处。

## 样例

样例调整量为 `+8, -8, +2, +9, -6, +1`。初值 5 的整卷读数为 `10, 2, 4, 10, 4, 5`，第 3、6 行应签为 `4, 5`，源出处分别为 `bench-a.log:103` 与 `bench-a.log:106`。同一实收件以 0 和 `1/2` 复核应得 `2, 5` 与 `5/2, 5`。第 3 行经下一班订正为 `+3` 后，新件以 5 签出 `5, 5`，原报告仍可按原号领取。
