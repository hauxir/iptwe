import base64
import re
import requests
from requests.structures import CaseInsensitiveDict


def parse_m3u(url):
    parsed = [
        dict(
            **CaseInsensitiveDict(
                r
                for r in [
                    [s for s in r.split("=", 1)]
                    for r in re.findall(r'\S+=".*?"', params)
                ]
            ),
            raw_params=params,
            url=url.strip()
        )
        for (params, url) in list(
            zip(
                *(
                    iter(
                        [
                            l
                            for l in requests.get(url).text.split("\n")
                            if not l.strip().startswith("#")
                            or l.strip().startswith("#EXTINF")
                        ]
                    ),
                )
                * 2
            )
        )
    ]
    result = []
    groups = list(
        set(
            [
                (val.get("group-title", "").lstrip('"').rstrip('"') or "???")
                for val in parsed
            ]
        )
    )
    for group in groups:
        result.append(dict(name=group or "???", channels=[]))
    if not groups:
        result.append(dict(name="???", channels=[]))
    for val in parsed:
        group_name = val.get("group-title", "???").lstrip('"').rstrip('"') or "???"
        group = next(g for g in result if g["name"] == group_name)
        group["channels"].append(
            dict(
                id=base64.b64encode(str.encode(val["url"])).decode("utf-8"),
                name=val.get(
                    "tvg-name",
                    val.get(
                        "tvg-id",
                        val.get("raw_params", "")[
                            val.get("raw_params", "").rfind(",") :
                        ],
                    ).lstrip(","),
                )
                .lstrip('"')
                .rstrip('"')
                .strip()
                or "???",
                logo=val.get("tvg-logo", "").lstrip('"').rstrip('"') or None,
            )
        )
    return result
