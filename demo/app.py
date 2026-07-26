import os, requests, streamlit as st
API_URL=os.getenv("VAULTAGENT_API_URL","http://127.0.0.1:8080")
st.set_page_config(page_title="VaultAgent v0.2",layout="wide")
st.title("VaultAgent v0.2")
st.caption("Local Qwen + protected DeepSeek delegation")
with st.sidebar:
    mode=st.selectbox("Execution mode",["LOCAL_ONLY","CLOUD_PLAN_LOCAL_EXECUTION",
                                       "PROTECTED_CONTEXT_CLOUD_REASONING"],index=2)
    purpose=st.selectbox("Purpose",["planning","personalized_tutoring"])
    confidentiality=st.selectbox("Confidentiality",
                                 ["PUBLIC","INTERNAL","CONFIDENTIAL","SECRET"],index=2)
    integrity=st.selectbox("Integrity",["TRUSTED","UNTRUSTED"])
query=st.text_area("User task","根据本地团队能力，为项目生成四周实施计划。")
knowledge=st.text_area("Local knowledge",
                       "张教授负责智能体安全项目，项目预算120万元。李工程师负责系统实现。",
                       height=150)
if st.button("Run",type="primary"):
    payload={"task":{"user_query":query,"purpose":purpose,"cloud_use_allowed":True,
                     "local_capability":0.25,"complexity":0.85,
                     "metadata":{"force_mode":mode,"privacy_scope_id":"synthetic-demo"}},
             "documents":[{"doc_id":"demo","content":knowledge,"source":"demo.txt",
                           "confidentiality":confidentiality,"integrity":integrity,
                           "allowed_purposes":[purpose],"allowed_sinks":["LOCAL_MODEL"]}]}
    try:
        response=requests.post(f"{API_URL}/v1/tasks/run",json=payload,timeout=240)
        response.raise_for_status(); result=response.json()
        left,right=st.columns(2)
        with left:
            st.subheader("Final local answer"); st.write(result["answer"])
            st.json({"mode":result["mode"],
                     "fallback":result["trace"]["fallback_chain"],
                     "models":result["trace"]["model_calls"]})
        with right:
            st.subheader("Cloud-visible payload"); st.json(result["trace"]["cloud_payload"])
            st.subheader("Protection"); st.json(result["trace"]["protection_decisions"])
    except Exception as exc:
        st.error(str(exc))
