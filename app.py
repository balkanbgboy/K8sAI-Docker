import subprocess
import tempfile
import yaml
import os
from dotenv import load_dotenv
from langchain_core.tools import tool, BaseTool
from langchain_classic.agents import create_tool_calling_agent, AgentExecutor
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

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

def apply_yaml(yaml_content: str):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        temp_file = f.name
        
    cmd = ["kubectl", "apply", "-f", temp_file]
    result = subprocess.run(cmd, capture_output=True, text=True)
    os.unlink(temp_file)
    return result.stdout if result.returncode == 0 else result.stderr
            
                            

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
    """Create a Kubernetes deployment. Input format example: name: web-app, image: httpd, replicas: 2"""
    name = None
    image = None
    replicas = 1

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

    yaml_content = generate_deployment_yaml(name, image, replicas)
    return apply_yaml(yaml_content)


@tool
def create_service(tool_input: str) -> str:
    """Create a Kubernetes service. Input format example: name: web-app, port: 80, type: ClusterIP"""
    name = None
    port = 80
    target_port = 80
    service_type = "ClusterIP"

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
    except Exception:
        pass
        
    if not name:
        raise ValueError("A 'name' must be provided to create a service.")

    yaml_content = generate_service_yaml(name, port=port, target_port=target_port, service_type=service_type)
    return apply_yaml(yaml_content)


tools = [create_deployment, create_service]

# Prompt
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant that creates Kubernetes deployments and services."),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

# Construct Agent
agent = create_tool_calling_agent(llm, tools, prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True, handle_parsing_errors=True)

if __name__ == "__main__":
    print("🤖 Kubernetes AI Agent Initialized")
    

    while True:
        try:
            user_input = input("\n💡 What should I do? (or 'exit'): ").strip()
            if user_input.lower() in ["exit", "quit"]:
                break
                
            result = agent_executor.invoke({
                "input": user_input,
                "chat_history": []
            })
                                     
            print("\nAgent Output:\n", result["output"])

                                                      
                                                      

                        
                                                   
                 
        except EOFError:
            print("\nNo input available. Exiting.")
            break
        except Exception as e:
            print(f"❌ Error: {e}")