load("//devtools/python/blaze:pytype.bzl", "pytype_strict_library")

pytype_strict_library(
    name = "test_agent",
    srcs = ["test_agent.py"],
    deps = [
        "//third_party/py/google/adk",
        "//third_party/py/google/adk:runners",
        "//third_party/py/google/genai",
    ],
)

pytype_strict_library(
    name = "test_agent_runtime_app",
    srcs = ["test_agent_runtime_app.py"],
    deps = [
        "//third_party/py/google/adk",
        "//third_party/py/pytest",
    ],
)
