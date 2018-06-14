custom_url = "xh=%s&xm=%s&gnmkdm=%s"
base_url = "http://jw2.jluzh.com/"
url_dict = {
    "score": "xscj_gc.aspx?",
    "timetable": "xskbcx.aspx?",
    "major_timetable": "tjkbcx.aspx?",
    "course_category": "xskc.aspx?",
    "selective_course": "xsxk.aspx?",
    "course_detail": "xsxjs.aspx?",
    "pe_class": "xstyk.aspx?",
    "evaluate_list": "xs_main.aspx?",
    "evaluate_teacher": "xsjxpj.aspx?"
}


def get_url(key, special=None):
    if key == "base":
        return base_url

    if special:
        url = "%s%s%s" % (base_url, url_dict[key], special)
    else:
        url = "%s%s%s" % (base_url, url_dict[key], custom_url)
    return url
