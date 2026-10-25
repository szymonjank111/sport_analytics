"""Stand-ins for the dbt_utils macros the models call, so sqlfluff can template them."""


def generate_surrogate_key(field_list: list[str]) -> str:
    return f"to_hex(md5(concat({', '.join(field_list)})))"
