load("//devtools/python/blaze:pytype.bzl", "pytype_strict_library")
load("//third_party/bazel_rules/rules_python/python:py_binary.bzl", "py_binary")
load("//third_party/bazel_rules/rules_python/python:py_library.bzl", "py_library")
load("//third_party/bazel_rules/rules_python/python:py_test.bzl", "py_test")

pytype_strict_library(
    name = "scratch/test_retrieval_flow",
    srcs = ["scratch/test_retrieval_flow.py"],
)

pytype_strict_library(
    name = "scratch/test_sidebar_search",
    srcs = ["scratch/test_sidebar_search.py"],
)

pytype_strict_library(
    name = "scratch/test_user_payload",
    srcs = ["scratch/test_user_payload.py"],
)

pytype_strict_library(
    name = "scratch/verify_deploy",
    srcs = ["scratch/verify_deploy.py"],
    deps = ["//third_party/py/google/genai"],
)

py_library(
    name = "pitchgen_multiagent_lib",
    srcs = glob(
        [
            "src/*.py",
            "src/agents/**/*.py",
            "src/pitchgen_app/**/*.py",
            "src/db/**/*.py",
            "src/orchestrators/**/*.py",
            "src/pitchgen_utils/**/*.py",
        ],
        exclude = [
            "src/pitchgen_utils/template_sorting.py",
        ],
    ),
    data = glob([
        "src/config/config.ini",
        "src/config/**/*.json",
        "src/prompt_templates/**/*.txt",
        "src/prompt_templates/**/*.json",
        "src/agents/skills/**/*.md",
        "src/agents/skills/**/*.json",
        "src/templates_metadata/**/*.txt",
        "src/templates_metadata/**/*.json",
    ]),
    imports = ["src"],
    strict_deps = False,
    visibility = ["//visibility:public"],
    deps = [
        ":config_loader",
        ":pitchgen_utils/template_sorting",
        "//third_party/py/dotenv",
        "//third_party/py/fuzzywuzzy",
        "//third_party/py/google/adk",
        "//third_party/py/google/adk:vertex_ai_session_service",
        "//third_party/py/google/cloud:core",
        "//third_party/py/google/cloud/aiplatform",
        "//third_party/py/google/cloud/discoveryengine_v1",
        "//third_party/py/google/cloud/logging",
        "//third_party/py/google/cloud/secretmanager",
        "//third_party/py/google/cloud/storage",
        "//third_party/py/google/cloud/translate_v3",
        "//third_party/py/google/genai",
        "//third_party/py/google/protobuf",
        "//third_party/py/googleapiclient",
        "//third_party/py/numpy",
        "//third_party/py/pydantic:pydantic_v2",
        "//third_party/py/pymysql",
        "//third_party/py/requests",
        "//third_party/py/sqlalchemy",
        "//third_party/py/vertexai",
    ],
)

py_binary(
    name = "test_slide_engineering",
    srcs = ["tests/test_slide_engineering.py"],
    deps = [
        ":pitchgen_multiagent_lib",
    ],
)

py_binary(
    name = "test_agent_workflow",
    srcs = ["tests/test_agent_workflow.py"],
    deps = [
        ":pitchgen_multiagent_lib",
        "//third_party/py/absl:app",
        "//third_party/py/urllib3",
    ],
)

pytype_strict_library(
    name = "tests/e2e_flow_validation",
    srcs = ["tests/e2e_flow_validation.py"],
)

py_test(
    name = "sidebar_agent_test",
    srcs = ["tests/sidebar_agent_test.py"],
    main = "tests/sidebar_agent_test.py",
    strict_deps = False,
    deps = [
        ":pitchgen_multiagent_lib",
    ],
)

pytype_strict_library(
    name = "tests/test_semantic_scoring_skill",
    srcs = ["tests/test_semantic_scoring_skill.py"],
    deps = ["//third_party/py/numpy"],
)

py_binary(
    name = "test_sidebar_integration",
    srcs = ["tests/test_sidebar_integration.py"],
    deps = [
        ":pitchgen_multiagent_lib",
        "//third_party/py/absl:app",
    ],
)

pytype_strict_library(
    name = "config_loader",
    srcs = ["src/config_loader.py"],
    imports = ["src"],
    deps = ["//third_party/py/google/cloud/secretmanager"],
)

py_library(
    name = "pitchgen_utils/template_sorting",
    srcs = ["src/pitchgen_utils/template_sorting.py"],
    imports = ["src"],
    strict_deps = False,
    deps = [
        ":config_loader",
        "//third_party/py/google/cloud/storage",
        "//third_party/py/google/genai",
    ],
)

pytype_strict_library(
    name = "main",
    srcs = ["main.py"],
)

py_binary(
    name = "adk_web_runner",
    srcs = ["run_adk.py"],
    main = "run_adk.py",
    deps = ["//third_party/py/google/adk:adk_cli"],
)

py_binary(
    name = "list_datastores",
    srcs = ["list_datastores.py"],
    deps = [
        "//third_party/py/google/cloud/discoveryengine_v1",
    ],
)

py_binary(
    name = "list_engines",
    srcs = ["list_engines.py"],
    deps = [
        ":pitchgen_multiagent_lib",
        "//third_party/py/google/cloud/aiplatform",
        "//third_party/py/vertexai",
    ],
)

py_binary(
    name = "test_synthesis_output",
    srcs = ["tests/test_synthesis_output.py"],
    deps = [
        ":pitchgen_multiagent_lib",
        "//third_party/py/google/genai",
    ],
)

pytype_strict_library(
    name = "scratch/check_datastore_schema",
    srcs = ["scratch/check_datastore_schema.py"],
    deps = [
        "//third_party/py/google/cloud/discoveryengine_v1",
        "//third_party/py/google/protobuf",
    ],
)

py_binary(
    name = "check_engines",
    srcs = ["scratch/check_engines.py"],
    deps = [
        "//third_party/py/google/auth:__init__",
        "//third_party/py/google/auth:transport/requests",
        "//third_party/py/requests",
    ],
)

pytype_strict_library(
    name = "scratch/check_results",
    srcs = ["scratch/check_results.py"],
)

pytype_strict_library(
    name = "scratch/check_secrets",
    srcs = ["scratch/check_secrets.py"],
    deps = [
        "//third_party/py/google/api_core",
        "//third_party/py/google/cloud/secretmanager",
    ],
)

pytype_strict_library(
    name = "scratch/check_session_db",
    srcs = ["scratch/check_session_db.py"],
    deps = ["//third_party/py/sqlite3"],
)

pytype_strict_library(
    name = "scratch/debug_secret",
    srcs = ["scratch/debug_secret.py"],
    deps = ["//third_party/py/google/cloud/secretmanager"],
)

py_binary(
    name = "explore_genai",
    srcs = ["scratch/explore_genai.py"],
    deps = ["//third_party/py/google/genai"],
)

pytype_strict_library(
    name = "scratch/extract_context",
    srcs = ["scratch/extract_context.py"],
)

pytype_strict_library(
    name = "scratch/extract_http_logs",
    srcs = ["scratch/extract_http_logs.py"],
)

pytype_strict_library(
    name = "scratch/fetch_web",
    srcs = ["scratch/fetch_web.py"],
)

pytype_strict_library(
    name = "scratch/find_server_command",
    srcs = ["scratch/find_server_command.py"],
)

pytype_strict_library(
    name = "scratch/get_tool_response",
    srcs = ["scratch/get_tool_response.py"],
    deps = ["//third_party/py/sqlite3"],
)

pytype_strict_library(
    name = "scratch/list_datastores",
    srcs = ["scratch/list_datastores.py"],
    deps = ["//third_party/py/google/cloud/discoveryengine_v1"],
)

pytype_strict_library(
    name = "scratch/list_secrets",
    srcs = ["scratch/list_secrets.py"],
    deps = ["//third_party/py/google/cloud/secretmanager"],
)

pytype_strict_library(
    name = "scratch/parse_search_log",
    srcs = ["scratch/parse_search_log.py"],
)

pytype_strict_library(
    name = "scratch/print_steps",
    srcs = ["scratch/print_steps.py"],
)

pytype_strict_library(
    name = "scratch/search_local",
    srcs = ["scratch/search_local.py"],
)

pytype_strict_library(
    name = "scratch/search_logs",
    srcs = ["scratch/search_logs.py"],
)

pytype_strict_library(
    name = "scratch/search_other_conv",
    srcs = ["scratch/search_other_conv.py"],
)

pytype_strict_library(
    name = "scratch/search_references",
    srcs = ["scratch/search_references.py"],
)

pytype_strict_library(
    name = "scratch/search_toyota",
    srcs = ["scratch/search_toyota.py"],
)

pytype_strict_library(
    name = "scratch/test_compliance",
    srcs = ["scratch/test_compliance.py"],
)

pytype_strict_library(
    name = "scratch/test_db_conn",
    srcs = ["scratch/test_db_conn.py"],
    deps = ["//third_party/py/sqlalchemy"],
)

pytype_strict_library(
    name = "scratch/test_embeddings",
    srcs = ["scratch/test_embeddings.py"],
    deps = [
        "//third_party/py/google/cloud/discoveryengine_v1",
        "//third_party/py/google/protobuf",
        "//third_party/py/numpy",
    ],
)

pytype_strict_library(
    name = "scratch/test_fallback",
    srcs = ["scratch/test_fallback.py"],
)

pytype_strict_library(
    name = "scratch/test_full_flow",
    srcs = ["scratch/test_full_flow.py"],
)
