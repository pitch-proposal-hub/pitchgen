load("//devtools/python/blaze:pytype.bzl", "pytype_strict_library")

pytype_strict_library(
    name = "skills",
    srcs = ["skills.py"],
    deps = [
        "//third_party/py/google/cloud/discoveryengine_v1",
        "//third_party/py/google/cloud/secretmanager",
        "//third_party/py/google/genai",
        "//third_party/py/requests",
    ],
)
