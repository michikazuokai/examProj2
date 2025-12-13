from exam2.models import Student, Subject, Exam, StudentExamVersion

# -------------------------------
# ① 事前に貼り付け YAML を Python dict にする
# -------------------------------

version_map = {
    "A": [
        24367002, 24367003, 24367005, 24367006,
        24367009, 24367010, 24367011, 24367015
    ],
    "B": [
        24367001, 24367004, 24367008, 24367012,
        24367013, 24367014, 24367016
    ]
}

subjectNo = "2030402"
fsyear = 2025
term = 2     # 今回の貼り付け YAML の「2」は学年扱い → term を 2 として使用


# -------------------------------
# ② Subject / Exam の取得
# -------------------------------
subject = Subject.objects.get(subjectNo=subjectNo)

exam_A = Exam.objects.get(subject=subject, fsyear=fsyear, term=term, version="A")
exam_B = Exam.objects.get(subject=subject, fsyear=fsyear, term=term, version="B")

print("Exam A:", exam_A)
print("Exam B:", exam_B)

# -------------------------------
# ③ StudentExamVersion の生成
# -------------------------------
created_count = 0

for version, stdno_list in version_map.items():
    for stdNo in stdno_list:

        student = Student.objects.get(stdNo=stdNo)

        exam = exam_A if version == "A" else exam_B

        obj, created = StudentExamVersion.objects.get_or_create(
            student=student,
            exam=exam,
        )

        if created:
            created_count += 1
            print(f"Created: {student.stdNo} → Exam {exam.id} ({version})")
        else:
            print(f"Exists:   {student.stdNo} → Exam {exam.id} ({version})")

print("------")
print("StudentExamVersion 作成完了:", created_count, "件")