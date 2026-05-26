import os
import pandas as pd
from pathlib import Path

# Create sample_seed_sources directory if it doesn't exist
seed_root = Path("sample_seed_sources")
seed_root.mkdir(exist_ok=True)

# Generate WoS seed
wos_path = seed_root / "wos-rare-earth.xlsx"
wos_rows = []
terms = ["dysprosium", "neodymium", "rare earth", "critical materials", "recycling", "separation"]
for index in range(80):
    term_a = terms[index % len(terms)]
    term_b = terms[(index + 2) % len(terms)]
    wos_rows.append({
        "UT": f"WOS:{index + 1:05d}",
        "TI": f"Rare earth {term_a} recovery route {index + 1}",
        "AB": f"This paper studies {term_a} and {term_b} recovery with rare earth recycling and separation.",
        "DE": f"rare earth; {term_a}; recycling",
        "ID": f"critical materials; {term_b}",
        "AU": "Li; Wang",
        "C1": "Example University; Materials Institute",
        "PY": 2018 + (index % 8),
        "SO": "Journal of Rare Earth Studies",
        "WC": "Materials Science",
        "DT": "Article",
        "DOI": f"10.1000/wos.{index + 1}",
    })
pd.DataFrame(wos_rows).to_excel(wos_path, index=False)
print(f"Generated mock WoS seed at {wos_path}")

# Generate IncoPat seed
incopat_path = seed_root / "incopat-rare-earth.xlsx"
incopat_rows = []
methods = ["萃取", "吸附", "磁选", "浸出", "回收", "分离"]
for index in range(80):
    method = methods[index % len(methods)]
    incopat_rows.append({
        "公开（公告）号": f"CN{index + 1:08d}A",
        "标题 (中文)": f"一种稀土{method}回收方法 {index + 1}",
        "摘要 (中文)": f"本发明涉及稀土材料的{method}、分离和回收利用，适用于磁性材料 and critical mineral processing.",
        "首项权利要求": f"一种包含{method}步骤的稀土回收工艺。",
        "技术功效短语": f"稀土回收; {method}; 磁性材料",
        "申请人": "示例科技大学; 稀土材料研究院",
        "发明人": "张三; 李四",
        "公开国别": "CN",
        "IPC": "C22B59/00",
        "公开（公告）日": pd.Timestamp(f"{2017 + (index % 9)}-06-15"),
        "被引证次数": index % 7,
        "引证次数": index % 5,
    })
pd.DataFrame(incopat_rows).to_excel(incopat_path, index=False)
print(f"Generated mock IncoPat seed at {incopat_path}")
