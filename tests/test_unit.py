import os
import yaml

os.environ.setdefault("GOOGLE_API_KEY", "ci-test-placeholder")

from app import (
    generate_deployment_yaml,
    generate_service_yaml,
    generate_namespace_yaml,
)


def test_deployment_basic():
    out = yaml.safe_load(generate_deployment_yaml("web", "nginx", replicas=3))
    assert out["kind"] == "Deployment"
    assert out["metadata"]["name"] == "web"
    assert out["metadata"]["namespace"] == "default"
    assert out["spec"]["replicas"] == 3
    assert out["spec"]["template"]["spec"]["containers"][0]["image"] == "nginx"


def test_deployment_custom_namespace():
    out = yaml.safe_load(generate_deployment_yaml("api", "httpd", namespace="staging"))
    assert out["metadata"]["namespace"] == "staging"


def test_service_defaults():
    out = yaml.safe_load(generate_service_yaml("web"))
    assert out["kind"] == "Service"
    assert out["metadata"]["name"] == "web-svc"
    assert out["spec"]["type"] == "ClusterIP"
    assert out["spec"]["ports"][0]["port"] == 80


def test_service_nodeport_custom_port():
    out = yaml.safe_load(generate_service_yaml("api", port=8080, target_port=8080, service_type="NodePort"))
    assert out["spec"]["type"] == "NodePort"
    assert out["spec"]["ports"][0]["port"] == 8080
    assert out["spec"]["ports"][0]["targetPort"] == 8080


def test_namespace_yaml():
    out = yaml.safe_load(generate_namespace_yaml("dev"))
    assert out["kind"] == "Namespace"
    assert out["metadata"]["name"] == "dev"


def test_deployment_selector_matches_labels():
    out = yaml.safe_load(generate_deployment_yaml("web", "nginx"))
    assert out["spec"]["selector"]["matchLabels"]["app"] == "web"
    assert out["spec"]["template"]["metadata"]["labels"]["app"] == "web"


def test_service_selector_matches_deployment_app_label():
    deploy = yaml.safe_load(generate_deployment_yaml("web", "nginx"))
    svc = yaml.safe_load(generate_service_yaml("web"))
    assert svc["spec"]["selector"] == deploy["spec"]["template"]["metadata"]["labels"]
