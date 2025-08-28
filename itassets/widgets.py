import json
from django import forms


class ReadonlyWidget(forms.HiddenInput):
    def __init__(self, f_display=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._f_display = f_display if f_display else lambda value: str(value) if value is not None else ""

    @property
    def is_hidden(self):
        return False

    def render(self, name, value, attrs=None, renderer=None):
        return "{}{}".format(super().render(name, value, attrs=attrs, renderer=renderer), self._f_display(value))


def _json_2_html(value):
    if not value:
        return '<table style="width:80%;height:50px"><tr><td style="border: 1px solid gray"></td></tr></table>'
    if isinstance(value, str):
        value = json.loads(value)
    if not value:
        return '<table style="width:80%;height:50px"><tr><td style="border: 1px solid gray"></td></tr></table>'
    else:
        return '<table><tr><td style="border: 1px solid gray"><pre>{}</pre></td></tr></table>'.format(json.dumps(value, indent=4))


text_readonly_widget = ReadonlyWidget(lambda value: "<pre>{}</pre>".format(value) if value else "")

textarea_readonly_widget = ReadonlyWidget(
    lambda value: '<table><tr><td style="border: 1px solid gray"><pre>{}</pre></td></tr></table>'.format(value)
    if value
    else '<table style="width:80%;height:50px"><tr><td style="border: 1px solid gray"></td></tr></table>'
)

json_readonly_widget = ReadonlyWidget(_json_2_html)

boolean_readonly_widget = ReadonlyWidget(
    lambda value: '<img src="/static/admin/img/icon-yes.svg" alt="True">'
    if value
    else '<img src="/static/admin/img/icon-no.svg" alt="True">'
)
