from __future__ import annotations

from types import MappingProxyType
from typing import Final, Mapping


CN_ADMIN_REGION_PROFILE: Final = "cn-admin-region-v1"

_CANONICAL_REGIONS = (
    "北京", "天津", "上海", "重庆",
    "河北", "山西", "辽宁", "吉林", "黑龙江", "江苏", "浙江", "安徽", "福建",
    "江西", "山东", "河南", "湖北", "湖南", "广东", "海南", "四川", "贵州", "云南",
    "陕西", "甘肃", "青海", "台湾", "内蒙古", "广西", "西藏", "宁夏", "新疆",
    "香港", "澳门",
    "石家庄", "太原", "沈阳", "长春", "哈尔滨", "南京", "杭州", "合肥", "福州",
    "南昌", "济南", "郑州", "武汉", "长沙", "广州", "海口", "成都", "贵阳", "昆明",
    "西安", "兰州", "西宁", "呼和浩特", "南宁", "拉萨", "银川", "乌鲁木齐",
    "深圳", "苏州", "厦门", "青岛", "宁波",
)


def _build_aliases() -> Mapping[str, str]:
    aliases: dict[str, str] = {}
    municipalities = {"北京", "天津", "上海", "重庆"}
    provinces = {
        "河北", "山西", "辽宁", "吉林", "黑龙江", "江苏", "浙江", "安徽", "福建", "江西",
        "山东", "河南", "湖北", "湖南", "广东", "海南", "四川", "贵州", "云南", "陕西",
        "甘肃", "青海", "台湾",
    }
    autonomous = {
        "内蒙古": "内蒙古自治区",
        "广西": "广西壮族自治区",
        "西藏": "西藏自治区",
        "宁夏": "宁夏回族自治区",
        "新疆": "新疆维吾尔自治区",
    }
    special = {"香港": "香港特别行政区", "澳门": "澳门特别行政区"}
    for canonical in _CANONICAL_REGIONS:
        aliases[canonical] = canonical
        aliases[f"{canonical}地区"] = canonical
        if canonical in municipalities or canonical not in provinces | set(autonomous) | set(special):
            aliases[f"{canonical}市"] = canonical
        if canonical in provinces:
            aliases[f"{canonical}省"] = canonical
    for canonical, full_name in autonomous.items():
        aliases[full_name] = canonical
    for canonical, full_name in special.items():
        aliases[full_name] = canonical
    return MappingProxyType(aliases)


CN_ADMIN_REGION_ALIASES: Final[Mapping[str, str]] = _build_aliases()


def normalize_admin_region(value: str, *, profile: str | None) -> str | None:
    if profile != CN_ADMIN_REGION_PROFILE:
        return None
    return CN_ADMIN_REGION_ALIASES.get(value)
