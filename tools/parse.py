from . import convert


__CONVERT_MAP__ = {
    "link": convert.Link,
    "img": convert.Img,
    "h1": convert.H1,
    "h2": convert.H2,
    "h3": convert.H3,
    "h4": convert.H4,
    "h5": convert.H5,
    "h6": convert.H6,
    "bold": convert.Bold,
    "italic": convert.Italic,
    "strikethrough": convert.Strikethrough,
    "blockQuote": convert.BlockQuote,
    "orderedList": convert.OrderedList,
    "unOrderedList": convert.UnOrderedList,
    "taskList": convert.TaskList,
    "table": convert.Table,
    "txt": convert.Txt,
    "code": convert.Code,
}


def parseToTxt(contents):
    res = []

    for item in contents:
        for key, value in item.items():
            obj = __CONVERT_MAP__[key]

            res.append(obj.toTxt(**value))

    return "".join(res)


def parseToHtml(contents) -> str:
    res = []

    for item in contents:
        for key, value in item.items():
            obj = __CONVERT_MAP__[key]

            res.append(obj.toHtml(**value))

    return "".join(res)


def parseToMarkdown(contents):
    res = []

    for item in contents:
        for key, value in item.items():
            obj = __CONVERT_MAP__[key]

            res.append(obj.toMd(**value))

    return "".join(res)


def parse(content, template="markdown"):
    if template == "markdown":
        return parseToMarkdown(content)
    elif template == "html":
        return parseToHtml(content)
    else:
        return parseToTxt(content)
