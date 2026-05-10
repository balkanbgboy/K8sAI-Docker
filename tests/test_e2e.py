import os
import subprocess
import time
import pytest

os.environ.setdefault("GOOGLE_API_KEY", "ci-test-placeholder")
os.environ.setdefault("K8S_OUTPUT_DIR", "/tmp/k8s-e2e")

from app import create_deployment, create_service

pytestmark = pytest.mark.e2e

NS = "ci-e2e"


def kubectl(*args, check=True):
    return subprocess.run(
        ["kubectl", *args],
        capture_output=True, text=True, check=check,
    )


@pytest.fixture(scope="module", autouse=True)
def cleanup_namespace():
    yield
    kubectl("delete", "namespace", NS, "--ignore-not-found", check=False)


def wait_for(predicate, timeout=60, interval=2):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


def test_create_deployment_in_custom_namespace():
    result = create_deployment.invoke(
        f"name: e2e-web, image: nginx, replicas: 1, namespace: {NS}"
    )
    assert "deployment.apps/e2e-web created" in result or "configured" in result

    ns = kubectl("get", "namespace", NS, "-o", "name")
    assert NS in ns.stdout

    deploy = kubectl("get", "deployment", "e2e-web", "-n", NS, "-o", "name")
    assert "deployment.apps/e2e-web" in deploy.stdout

    ready = wait_for(
        lambda: "1/1" in kubectl(
            "get", "deployment", "e2e-web", "-n", NS,
            "--no-headers", check=False,
        ).stdout
    )
    assert ready, "deployment never became ready within timeout"


def test_create_service_in_same_namespace():
    result = create_service.invoke(
        f"name: e2e-web, port: 80, type: ClusterIP, namespace: {NS}"
    )
    assert "service/e2e-web-svc created" in result or "configured" in result

    svc = kubectl("get", "service", "e2e-web-svc", "-n", NS, "-o", "yaml")
    assert "type: ClusterIP" in svc.stdout
    assert "app: e2e-web" in svc.stdout
