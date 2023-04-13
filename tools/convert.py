class Convert:
    @staticmethod
    def toTxt(content, newLine="\n", **kwargs) -> str:
        return f"{content}{newLine}"

    @staticmethod
    def toMd(content, newLine="\n", **kwargs) -> str:
        return f"{content}{newLine}"

    @staticmethod
    def toHtml(content, **kwargs) -> str:
        return f"<div>{content}</div>"


class OrderedList(Convert):
    @staticmethod
    def toTxt(content, newLine="\n", **kwargs) -> str:
        res = []

        for index, value in enumerate(content):
            res.append(f"{index+1}. {value}{newLine}")

        return "".join(res)

    @staticmethod
    def toMd(content, newLine="\n", **kwargs) -> str:
        res = []

        for index, value in enumerate(content):
            content.append(f"{index}. {value}{newLine}")

        return "".join(res)

    @staticmethod
    def toHtml(content, **kwargs) -> str:
        ol = ["<ol"]

        style = kwargs.get("style")

        if style is not None:
            ol.append(f"style='{style}'")

        ol.append(">")

        for item in content:
            ol.append(f"<li>{item}</li>")

        ol.append("</ol>")

        return " ".join(ol)


class UnOrderedList(Convert):
    @staticmethod
    def toTxt(content, newLine="\n", **kwargs) -> str:
        res = []

        for value in content:
            res.append(f"· {value}{newLine}")

        return "".join(res)

    @staticmethod
    def toMd(content, newLine="\n", **kwargs) -> str:
        res = []

        for value in content:
            content.append(f"- {value}{newLine}")

        return "".join(res)

    @staticmethod
    def toHtml(content, **kwargs) -> str:
        ul = ["<ul"]

        style = kwargs.get("style")

        if style is not None:
            ul.append(f"style='{style}'")

        ul.append(">")

        for item in content:
            ul.append(f"<li>{item}</li>")

        ul.append("</ul>")

        return " ".join(ul)


__H_HTML__ = ["", "h1", "h2", "h3", "h4", "h5", "h6"]
__H_MD__ = ["", "#", "##", "###", "####", "#####", "######"]


class H(Convert):
    @staticmethod
    def toTxt(content, newLine="\n", **kwargs) -> str:
        return Convert.toTxt(content, newLine, **kwargs)

    @staticmethod
    def toMd(level, content, newLine="\n", **kwargs) -> str:
        tag = __H_MD__[level]

        return f"{tag} {content}{newLine}"

    @staticmethod
    def toHtml(level, content, **kwargs) -> str:
        tag = __H_HTML__[level]

        h = [f"<{tag}"]

        style = kwargs.get("style")

        if style is not None:
            h.append(f"style='{style}'")

        h.append(f">{content}</{tag}>")

        return " ".join(h)


class H1(H):
    @staticmethod
    def toTxt(content, newLine="\n", **kwargs) -> str:
        return Convert.toTxt(content, newLine, **kwargs)

    @staticmethod
    def toMd(content, newLine="\n", **kwargs) -> str:
        return H.toMd(1, content, newLine, **kwargs)

    @staticmethod
    def toHtml(content, **kwargs) -> str:
        return H.toHtml(1, content, **kwargs)


class H2(H):
    @staticmethod
    def toTxt(content, newLine="\n", **kwargs) -> str:
        return Convert.toTxt(content, newLine, **kwargs)

    @staticmethod
    def toMd(content, newLine="\n", **kwargs) -> str:
        return H.toMd(2, content, newLine, **kwargs)

    @staticmethod
    def toHtml(content, **kwargs) -> str:
        return H.toHtml(2, content, **kwargs)


class H3(H):
    @staticmethod
    def toTxt(content, newLine="\n", **kwargs) -> str:
        return Convert.toTxt(content, newLine, **kwargs)

    @staticmethod
    def toMd(content, newLine="\n", **kwargs) -> str:
        return H.toMd(3, content, newLine, **kwargs)

    @staticmethod
    def toHtml(content, **kwargs) -> str:
        return H.toHtml(3, content, **kwargs)


class H4(H):
    @staticmethod
    def toTxt(content, newLine="\n", **kwargs) -> str:
        return Convert.toTxt(content, newLine, **kwargs)

    @staticmethod
    def toMd(content, newLine="\n", **kwargs) -> str:
        return H.toMd(4, content, newLine, **kwargs)

    @staticmethod
    def toHtml(content, **kwargs) -> str:
        return H.toHtml(4, content, **kwargs)


class H5(H):
    @staticmethod
    def toTxt(content, newLine="\n", **kwargs) -> str:
        return Convert.toTxt(content, newLine, **kwargs)

    @staticmethod
    def toMd(content, newLine="\n", **kwargs) -> str:
        return H.toMd(5, content, newLine, **kwargs)

    @staticmethod
    def toHtml(content, **kwargs) -> str:
        return H.toHtml(5, content, **kwargs)


class H6(H):
    @staticmethod
    def toTxt(content, newLine="\n", **kwargs) -> str:
        return Convert.toTxt(content, newLine, **kwargs)

    @staticmethod
    def toMd(content, newLine="\n", **kwargs) -> str:
        return H.toMd(6, content, newLine, **kwargs)

    @staticmethod
    def toHtml(content, **kwargs) -> str:
        return H.toHtml(6, content, **kwargs)


class Img(Convert):
    """
    Img.toHtml("http://1.png", style="width: 100px", alt="1")
    """

    @staticmethod
    def toTxt(url, newLine="\n", **kwargs) -> str:
        alt = kwargs.get("alt", "link")

        return f"{alt}: {url}{newLine}"

    @staticmethod
    def toMd(url, newLine="\n", **kwargs) -> str:
        alt = kwargs.get("alt", "No alt")

        return f"![{alt}]({url}){newLine}"

    @staticmethod
    def toHtml(url, **kwargs) -> str:
        res = []

        alt = kwargs.get("alt", "No alt")

        res.append(f"<img src='{url}' alt='{alt}'")

        style = kwargs.get("style")

        if style is not None:
            res.append(f"style='{style}'")

        res.append("/>")

        return " ".join(res)


class Link(Convert):
    """
    Link.toHtml("https://xxx", content="this is a link", style="color: blue")

    and

    Link.toHtml("https://xxx")
    """

    @staticmethod
    def toTxt(url, newLine="\n", **kwargs) -> str:
        content = kwargs.get("content", "link")

        return f"{content}: {url}{newLine}"

    @staticmethod
    def toMd(url, newLine="\n", **kwargs) -> str:
        content = kwargs.get("content", "link")

        return f"[{content}]({url}){newLine}"

    @staticmethod
    def toHtml(url, **kwargs) -> str:
        res = []

        content = kwargs.get("content", "link")

        style = kwargs.get("style")

        res.append(f"<a href='{url}'")

        if style is not None:
            res.append(f"style='{style}'")

        res.append(f">{content}</a>")

        return " ".join(res)


class Table(Convert):
    """
    Table.toHtml(
        [
            ("标题", "内容"),
            ("1", "A"),
            ("2", "B"),
        ],
        style="border: 1px",
        thStyle="padding: 1px",
        tdStyle="padding: 1px",
    )

    or

    Table.toMd(
        [
            ("标题", "内容"),
            ("1", "A"),
            ("2", "B"),
        ],
        position="left",
        newline="\n",
    )
    """

    @staticmethod
    def toTxt(contents, newLine="\n", **kwargs) -> str:
        res = ["\n"]

        for item in contents:
            for i in item:
                res.append(f"{i}\t")

            res.append(newLine)

        return "".join(res) + "\n"

    @staticmethod
    def toMd(contents, newLine="\n", **kwargs) -> str:
        res = ["\n"]

        for i in contents[0]:
            res.append(f"|{i}")

        res.append(f"|{newLine}")

        position = kwargs.get("position", "center")

        if position == "center":
            s = ":--:"
        elif position == "left":
            s = ":--"
        else:
            s = "--:"

        for _ in range(len(contents[0])):
            res.append(f"|{s}")

        res.append(f"|{newLine}")

        for tuple_ in contents[1:]:
            for i in tuple_:
                res.append(f"|{i}")

            res.append(f"|{newLine}")

        return "".join(res) + "\n"

    @staticmethod
    def toHtml(contents, **kwargs) -> str:
        style = kwargs.get(
            "style", "width: 100%; border-collapse: collapse; margin-bottom: 10px;"
        )

        thStyle = kwargs.get(
            "thStyle",
            "text-align: center; border: 1px solid #e6e6e6; background-color: #F5F5F5;",
        )

        tdStyle = kwargs.get(
            "tdStyle", "text-align: center; border: 1px solid #e6e6e6;"
        )

        tb = ["<table"]

        tb.append(f"style='{style}'><tr>")

        for i in contents[0]:
            tb.append(f"<th style='{thStyle}'>{i}</th>")

        tb.append("</tr>")

        for item in contents[1:]:
            tb.append("<tr>")

            for i in item:
                tb.append(f"<td style='{tdStyle}'>{i}</td>")

            tb.append("</tr>")

        tb.append("</table>")

        return " ".join(tb)


class Txt(Convert):
    @staticmethod
    def toTxt(content, newLine="\n", **kwargs) -> str:
        return Convert.toTxt(content, newLine, **kwargs)

    @staticmethod
    def toMd(content, newLine="\n", **kwargs) -> str:
        return Convert.toMd(content, newLine, **kwargs)

    @staticmethod
    def toHtml(content, **kwargs) -> str:
        return Convert.toHtml(content, **kwargs)


class Bold(Convert):
    @staticmethod
    def toTxt(content, newLine="", **kwargs) -> str:
        return Convert.toTxt(content, newLine, **kwargs)

    @staticmethod
    def toMd(content, newLine="", **kwargs) -> str:
        return f"**{content}**{newLine}"

    @staticmethod
    def toHtml(content, **kwargs) -> str:
        res = ["<strong"]

        style = kwargs.get("style")

        if style:
            res.append(f"style='{style}'")

        res.append(f">{content}</strong>")

        return " ".join(res)


class Italic(Convert):
    @staticmethod
    def toTxt(content, newLine="", **kwargs) -> str:
        return Convert.toTxt(content, newLine, **kwargs)

    @staticmethod
    def toMd(content, newLine="", **kwargs) -> str:
        return f"*{content}*{newLine}"

    @staticmethod
    def toHtml(content, **kwargs) -> str:
        res = ["<i"]

        style = kwargs.get("style")

        if style:
            res.append(f"style='{style}'")

        res.append(f">{content}</i>")

        return " ".join(res)


class Strikethrough(Convert):
    @staticmethod
    def toTxt(content, newLine="", **kwargs) -> str:
        return Convert.toTxt(content, newLine, **kwargs)

    @staticmethod
    def toMd(content, newLine="", **kwargs) -> str:
        return f"~~{content}~~{newLine}"

    @staticmethod
    def toHtml(content, **kwargs) -> str:
        res = ["<del"]

        style = kwargs.get("Style")

        if style is not None:
            res.append(f"style='{style}'")

        res.append(f">{content}</del>")

        return " ".join(res)


class BlockQuote(Convert):
    @staticmethod
    def toTxt(content, newLine="\n", **kwargs) -> str:
        return Convert.toTxt(content, newLine, **kwargs)

    @staticmethod
    def toMd(content, newLine="\n", **kwargs) -> str:
        return f"> {content}{newLine}"

    @staticmethod
    def toHtml(content, **kwargs) -> str:
        res = ["<blockquote"]

        style = kwargs.get("style")

        if style:
            res.append(f"style='{style}'")

        res.append(f">{content}</blockquote>")

        return " ".join(res)


class TaskList(Convert):
    """
    TaskList([
        {
            "content": "run 100 kilometers",
            "style": "color: red",
        },
        {
            "content": "do homeworks",
            "complete": True
        },
    ])
    """

    @staticmethod
    def toTxt(contents, newLine="\n", **kwargs) -> str:
        return TaskList.toMd(contents, newLine, **kwargs)

    @staticmethod
    def toMd(contents, newLine="\n", **kwargs) -> str:
        res = []

        for item in contents:
            completed = item.get("complete", False)
            content = item.get("content")

            if completed:
                res.append(f"- [x] {content}{newLine}")
            else:
                res.append(f"- [ ] {content}{newLine}")

        return "".join(res)

    @staticmethod
    def toHtml(contents, **kwargs) -> str:
        res = []

        for item in contents:
            completed = item.get("complete", False)
            content = item.get("content")
            style = item.get("Style")

            res.append("<label><input type='checkbox' disabled='true'")

            if style is not None:
                res.append(f"style='{style}'")

            if completed:
                res.append(f"checked='checked'/>{content}</label>")
            else:
                res.append(f"/>{content}</label>")

        return " ".join(res)


class Code(Convert):
    @staticmethod
    def toTxt(content, newLine="\n", **kwargs) -> str:
        return f"{content}{newLine}"

    @staticmethod
    def toMd(content, newLine="\n", **kwargs) -> str:
        return f"`{content}`{newLine}"

    @staticmethod
    def toHtml(content, **kwargs) -> str:
        return f"<pre>{content}</pre>"
