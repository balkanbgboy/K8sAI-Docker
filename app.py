import subprocess
import shutil
import yaml
import os
from dotenv import load_dotenv
from langchain_core.tools import tool, BaseTool
from langchain_classic.agents import create_tool_calling_agent, AgentExecutor
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage

load_dotenv()

# Initialize LLM
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=os.getenv("GOOGLE_API_KEY"),
    temperature=0.1,
    max_tokens=2048
)

# --- Deployment Helpers ---
def generate_deployment_yaml(name: str, image: str, replicas: int = 1, namespace: str = "default", port: int = 80):
    deployment = {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {"name": name, "namespace": namespace},
        "spec": {
            "replicas": replicas,
            "selector": {"matchLabels": {"app": name}},
            "template": {
                "metadata": {"labels": {"app": name}},
                "spec": {
                    "containers": [{
                        "name": name,
                        "image": image,
                        "ports": [{"containerPort": port}]
                    }]
                }
            }
        }
    }
    return yaml.dump(deployment, default_flow_style=False)

def _kubectl_env():
    env = os.environ.copy()
    extra_paths = ["/usr/local/bin", "/usr/bin", "/snap/bin"]
    env["PATH"] = ":".join([env.get("PATH", "")] + extra_paths).strip(":")
    if not env.get("KUBECONFIG"):
        for candidate in ("/root/.kube/config", os.path.expanduser("~/.kube/config")):
            if os.path.isfile(candidate):
                env["KUBECONFIG"] = candidate
                break
    return env

def _kubectl_bin():
    explicit = os.environ.get("KUBECTL")
    if explicit and os.path.isfile(explicit):
        return explicit
    found = shutil.which("kubectl")
    if found:
        return found
    for candidate in ("/usr/local/bin/kubectl", "/usr/bin/kubectl", "/snap/bin/kubectl"):
        if os.path.isfile(candidate):
            return candidate
    return None

K8S_OUTPUT_DIR = os.environ.get("K8S_OUTPUT_DIR", "/k8s")

def save_yaml(yaml_content: str, filename: str) -> str:
    os.makedirs(K8S_OUTPUT_DIR, exist_ok=True)
    path = os.path.join(K8S_OUTPUT_DIR, filename)
    with open(path, "w") as f:
        f.write(yaml_content)
    return path

def apply_yaml_file(path: str) -> str:
    kubectl = _kubectl_bin()
    if not kubectl:
        return "kubectl not found on PATH. Set the KUBECTL env var to its absolute path, or install kubectl in this environment."

    result = subprocess.run(
        [kubectl, "apply", "-f", path],
        capture_output=True, text=True, env=_kubectl_env(),
    )
    if result.returncode != 0:
        return f"kubectl failed (rc={result.returncode}):\nSTDERR: {result.stderr.strip()}\nSTDOUT: {result.stdout.strip()}"
    return result.stdout
            
                            

# --- Namespace Helper ---
def generate_namespace_yaml(name: str):
    ns = {
        "apiVersion": "v1",
        "kind": "Namespace",
        "metadata": {"name": name},
    }
    return yaml.dump(ns, default_flow_style=False)

def ensure_namespace(namespace: str) -> str:
    if namespace == "default" or not namespace:
        return ""
    yaml_content = generate_namespace_yaml(namespace)
    path = save_yaml(yaml_content, f"{namespace}-namespace.yaml")
    apply_result = apply_yaml_file(path)
    return f"Namespace manifest: {path}\n{apply_result}\n"

# --- Service Helper ---
def generate_service_yaml(name: str, namespace: str = "default", port: int = 80, target_port: int = 80, service_type: str = "ClusterIP"):
    service = {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {"name": f"{name}-svc", "namespace": namespace},
        "spec": {
            "selector": {"app": name},
            "ports": [{
                "port": port,
                "targetPort": target_port,
                "protocol": "TCP",
                "name": "http"
            }],
            "type": service_type
        }
    }
    return yaml.dump(service, default_flow_style=False)

# --- Tools ---

@tool
def create_deployment(tool_input: str) -> str:
    """Create a Kubernetes deployment. Always ask the user for the namespace before calling this tool; if they don't specify one, ask explicitly. If the namespace is not 'default', it will be created automatically. Input format example: name: web-app, image: httpd, replicas: 2, namespace: staging"""
    name = None
    image = None
    replicas = 1
    namespace = "default"

    tool_input = tool_input.strip().strip("{}'\"")

    # Try to parse key-value pairs
    try:
        parts = tool_input.split(",")
        for part in parts:
            if ":" in part:
                k, v = part.split(":", 1)
                k, v = k.strip().strip("'\""), v.strip().strip("'\"")
                if k == "name":
                    name = v
                elif k == "image":
                    image = v
                elif k == "replicas":
                    replicas = int(v)
                elif k == "namespace":
                    namespace = v
    except Exception:
        pass

    # Fallback to space separated if the dictionary format fails
    if not name or not image:
        parts = tool_input.split()
        if len(parts) >= 2:
            name = parts[0].replace("name:", "").strip()
            image = parts[1].replace("image:", "").strip()

            if len(parts) > 2:
                try:
                    replicas_val = parts[2].replace("replicas:", "").strip()
                    replicas = int(replicas_val)
                except ValueError:
                    pass

    if not name or not image:
        raise ValueError("Both 'name' and 'image' must be provided to create a deployment.")

    ns_result = ensure_namespace(namespace)

    yaml_content = generate_deployment_yaml(name, image, replicas, namespace=namespace)
    path = save_yaml(yaml_content, f"{name}-deployment.yaml")
    apply_result = apply_yaml_file(path)
    return f"{ns_result}Saved manifest: {path}\n{apply_result}"


@tool
def create_service(tool_input: str) -> str:
    """Create a Kubernetes service. Always ask the user for the namespace before calling this tool; if they don't specify one, ask explicitly. If the namespace is not 'default', it will be created automatically. Input format example: name: web-app, port: 80, type: ClusterIP, namespace: staging"""
    name = None
    port = 80
    target_port = 80
    service_type = "ClusterIP"
    namespace = "default"

    tool_input = tool_input.strip().strip("{}'\"")

    try:
        parts = tool_input.split(",")
        for part in parts:
            if ":" in part:
                k, v = part.split(":", 1)
                k, v = k.strip().strip("'\""), v.strip().strip("'\"")
                if k == "name":
                    name = v
                elif k == "port":
                    port = int(v)
                elif k == "target_port":
                    target_port = int(v)
                elif k == "type":
                    service_type = v
                elif k == "namespace":
                    namespace = v
    except Exception:
        pass

    if not name:
        raise ValueError("A 'name' must be provided to create a service.")

    ns_result = ensure_namespace(namespace)

    yaml_content = generate_service_yaml(name, namespace=namespace, port=port, target_port=target_port, service_type=service_type)
    path = save_yaml(yaml_content, f"{name}-service.yaml")
    apply_result = apply_yaml_file(path)
    return f"{ns_result}Saved manifest: {path}\n{apply_result}"


tools = [create_deployment, create_service]

# Prompt
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant that creates Kubernetes deployments and services. Before creating any deployment or service, first ask the user whether to deploy to the 'default' namespace or a different one. If they pick a different namespace, ask them for its exact name. The chosen namespace will be created automatically if it does not already exist. Never assume a namespace without asking."),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

# Construct Agent
agent = create_tool_calling_agent(llm, tools, prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=False, handle_parsing_errors=True)

def format_output(output):
    if isinstance(output, str):
        return output
    if isinstance(output, dict):
        return output.get("text") or output.get("content") or str(output)
    if isinstance(output, list):
        parts = []
        for item in output:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if text:
                    parts.append(text)
        joined = "\n".join(p for p in parts if p)
        return joined if joined else str(output)
    return str(output)

if __name__ == "__main__":
    print("🤖 Kubernetes AI Agent Initialized")

    chat_history = []

    while True:
        try:
            user_input = input("\n💡 What should I do? (or 'exit'): ").strip()
            if user_input.lower() in ["exit", "quit"]:
                break

            result = agent_executor.invoke({
                "input": user_input,
                "chat_history": chat_history,
            })

            output_text = format_output(result["output"])
            print("\nAgent Output:\n", output_text)

            chat_history.append(HumanMessage(content=user_input))
            chat_history.append(AIMessage(content=output_text))

                                                      
                                                      

                        
                                                   
                 
        except EOFError:
            print("\nNo input available. Exiting.")
            break
        except Exception as e:
            print(f"❌ Error: {e}")