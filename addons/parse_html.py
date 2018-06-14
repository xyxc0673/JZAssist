from bs4 import BeautifulSoup
from .errors import PageError


def parse_standard_table(html, id_name=None, class_name=None, keys=None, pure=False):
    soup = BeautifulSoup(html, "html5lib")
    if id_name:
        table = soup.find(id=id_name)
    elif class_name:
        table = soup.find(class_=class_name)
    else:
        table = soup.find("table")

    if not table:
        raise PageError("Error!")

    skip_tr = 1
    pure_result = []
    zipped_result = []

    trs = table.find_all("tr")
    for tr in trs:
        if skip_tr > 0:
            skip_tr -= 1
            continue
        if "nowrap" in tr.attrs:
            continue

        row = []
        tds = tr.find_all("td")
        for td in tds:
            if "style" in td.attrs:
                if "display:none" in td.attrs["style"]:
                    continue
            row.append(td.text.strip().replace("[", "").replace("]", ""))
        if pure:
            pure_result.append(row)
        else:
            zipped_result.append(dict(zip(keys, row)))
    if pure:
        return pure_result
    return zipped_result