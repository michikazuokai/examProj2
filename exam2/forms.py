# exam2/forms.py
from django import forms
from exam2.models import Subject

class ManageStdVersionSubjectForm(forms.Form):
    subject = forms.ModelChoiceField(
        label="科目（subjectNo / fsyear / name）",
        queryset=Subject.objects.all().order_by("-fsyear", "subjectNo"),
        empty_label="-- 科目を選択 --",
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["subject"].label_from_instance = (
            lambda s: f"{s.subjectNo} / {s.fsyear} / {getattr(s, 'name', '')}"
        )