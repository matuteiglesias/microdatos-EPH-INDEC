# ENGHo 2017/18 M1 real-data commissioning receipt

## Decision

The governed `publicdata.indec-engho-microdata/v1` capability was executed against the official ENGHo 2017/18 public-use source family and passed real-data commissioning with one explicit custody warning.

Producer commit:

```text
22f15527c1f504e924032df270b4e1d05777fc0f
```

Release identity:

```text
engho-2017-2018-ff05578d65ae
```

Status:

```text
PASS with explicit warning
```

## Inventory

| Role | Rows | Columns |
| --- | ---: | ---: |
| households | 21,547 | 134 |
| persons | 68,725 | 158 |
| expenditures | 901,804 | 19 |
| articles | 1,224 | 10 |
| replicate weights | 21,547 | 201 |

Source delimiter is `|`. Source text is UTF-8-SIG and normalized text is UTF-8.

All five required table roles and required identity fields were present. The release validator passed. A deterministic re-extraction produced the same release ID and identical normalized table payloads.

The immutable local release and commissioning receipt record the exact official source hashes and release-manifest hash. They are not duplicated here because this repository receipt is deliberately compact and contains no respondent-level material.

## Explicit warning

The persons table contains 68,725 rows, while the published manual count used by commissioning is 68,675: a difference of 50 rows.

This was adjudicated as a custody warning rather than a filter condition because:

- source keys are unique;
- all source rows were retained;
- no recoding or scientific filtering was applied.

Downstream consumers must not silently delete 50 rows merely to reproduce the manual total.

## Boundary

This receipt proves acquisition/republication and deterministic custody only.

It does **not** authorize:

- p29–p48 selection;
- expenditure-share construction;
- food/non-food classification;
- Engel coefficients;
- CBA/CBT construction;
- poverty estimation.

Those remain downstream scientific responsibilities.

No raw or normalized respondent-level ENGHo table is committed to git.
