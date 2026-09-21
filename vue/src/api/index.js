// 全部后端接口封装（前缀 /api 已在 request.js baseURL 中）
import http from '@/utils/request'

const get = (url, params) => http.get(url, { params })
const post = (url, data, cfg) => http.post(url, data, cfg)
const put = (url, data) => http.put(url, data)
const del = (url) => http.delete(url)

// ---------------- 认证 ----------------
export const apiLogin = (data) => post('/login', data)
export const apiRegister = (data) => post('/register', data)
export const apiMe = () => get('/auth/me')
export const apiUpdateProfile = (data) => put('/auth/profile', data)
export const apiChangePassword = (data) => put('/auth/password', data)

// ---------------- 首页统计 ----------------
export const apiDashboardSummary = () => get('/dashboard/summary')

// ---------------- 用户管理 / 操作日志 ----------------
export const apiUserPage = (params) => get('/admin/user/page', params)
export const apiUserCreate = (data) => post('/admin/user', data)
export const apiUserUpdate = (uid, data) => put(`/admin/user/${uid}`, data)
export const apiUserStatus = (uid, data) => put(`/admin/user/${uid}/status`, data)
export const apiUserResetPwd = (uid, data) => put(`/admin/user/${uid}/password`, data)
export const apiUserDelete = (uid) => del(`/admin/user/${uid}`)
export const apiOperationLogPage = (params) => get('/operationLog/page', params)

// ---------------- AI 模型配置 ----------------
export const apiModelPage = (params) => get('/aiModel/page', params)
export const apiModelCreate = (data) => post('/aiModel', data)
export const apiModelUpdate = (mid, data) => put(`/aiModel/${mid}`, data)
export const apiModelDelete = (mid) => del(`/aiModel/${mid}`)
export const apiModelEnable = (mid, data) => put(`/aiModel/${mid}/enable`, data)
export const apiModelTest = (mid) => post(`/aiModel/${mid}/test`)

// ---------------- Prompt 模板 ----------------
export const apiPromptPage = (params) => get('/prompt/page', params)
export const apiPromptCreate = (data) => post('/prompt', data)
export const apiPromptUpdate = (pid, data) => put(`/prompt/${pid}`, data)
export const apiPromptDelete = (pid) => del(`/prompt/${pid}`)
export const apiPromptImportBuiltin = () => post('/prompt/import_builtin')

// ---------------- 工具中心 ----------------
export const apiToolPage = (params) => get('/tool/page', params)
export const apiToolCreate = (data) => post('/tool', data)
export const apiToolUpdate = (tid, data) => put(`/tool/${tid}`, data)
export const apiToolDelete = (tid) => del(`/tool/${tid}`)
export const apiToolImportBuiltin = () => post('/tool/import_builtin')
export const apiToolExecute = (data) => post('/tool/execute', data)
export const apiToolLogPage = (params) => get('/tool/log/page', params)

// ---------------- 知识库 ----------------
export const apiKbPage = (params) => get('/knowledgeBase/page', params)
export const apiKbOptions = () => get('/knowledgeBase/options')
export const apiKbCreate = (data) => post('/knowledgeBase', data)
export const apiKbUpdate = (kid, data) => put(`/knowledgeBase/${kid}`, data)
export const apiKbDelete = (kid) => del(`/knowledgeBase/${kid}`)
export const apiKbBatchDelete = (data) => post('/knowledgeBase/batch_delete', data)
export const apiKbRebuild = (kid) => post(`/knowledgeBase/${kid}/rebuild`)
export const apiKbRebuildStatus = (kid) => get(`/knowledgeBase/${kid}/rebuild_status`)

// ---------------- 切分策略 ----------------
export const apiSplitPage = (params) => get('/splitStrategy/page', params)
export const apiSplitOptions = () => get('/splitStrategy/options')
export const apiSplitCreate = (data) => post('/splitStrategy', data)
export const apiSplitUpdate = (sid, data) => put(`/splitStrategy/${sid}`, data)
export const apiSplitDelete = (sid) => del(`/splitStrategy/${sid}`)

// ---------------- 检索策略 ----------------
export const apiRetrievalPage = (params) => get('/retrievalStrategy/page', params)
export const apiRetrievalOptions = () => get('/retrievalStrategy/options')
export const apiRetrievalCreate = (data) => post('/retrievalStrategy', data)
export const apiRetrievalUpdate = (sid, data) => put(`/retrievalStrategy/${sid}`, data)
export const apiRetrievalDelete = (sid) => del(`/retrievalStrategy/${sid}`)

// ---------------- 文档管理 ----------------
export const apiDocUpload = (formData) =>
  post('/document/upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } })
export const apiDocPage = (params) => get('/document/page', params)
export const apiDocReparse = (docId) => post(`/document/${docId}/reparse`)
export const apiDocDelete = (docId) => del(`/document/${docId}`)
export const apiDocBatchDelete = (data) => post('/document/batch_delete', data)

// ---------------- 片段管理 ----------------
export const apiChunkPage = (params) => get('/chunk/page', params)
export const apiChunkUpdate = (cid, data) => put(`/chunk/${cid}`, data)
export const apiChunkStatus = (cid, data) => put(`/chunk/${cid}/status`, data)
export const apiChunkDetail = (cid) => get(`/chunk/${cid}`)

// ---------------- 检索测试 / 召回调试台 ----------------
export const apiRetrievalTest = (data) => post('/retrieval/test', data)
export const apiRetrievalCompare = (data) => post('/retrieval/compare', data)

// ---------------- Agent ----------------
export const apiAgentRun = (data) => post('/agent/run', data)
export const apiAgentRunPage = (params) => get('/agent/runPage', params)
export const apiAgentRunDetail = (runId) => get(`/agent/run/${runId}`)
export const apiAgentSteps = (runId) => get(`/agent/steps/${runId}`)

// ---------------- 问答应用 ----------------
export const apiChatAppPage = (params) => get('/chatApp/page', params)
export const apiChatAppOptions = () => get('/chatApp/options')
export const apiChatAppCreate = (data) => post('/chatApp', data)
export const apiChatAppUpdate = (aid, data) => put(`/chatApp/${aid}`, data)
export const apiChatAppBindKbs = (aid, data) => put(`/chatApp/${aid}/kbs`, data)
export const apiChatAppDelete = (aid) => del(`/chatApp/${aid}`)

// ---------------- 会话（用户端问答） ----------------
export const apiSessionPage = (params) => get('/chat/session/page', params)
export const apiSessionCreate = (data) => post('/chat/session', data)
export const apiSessionDelete = (sid) => del(`/chat/session/${sid}`)
export const apiChatHistory = (sid) => get(`/chat/history/${sid}`)
export const apiChatFeedback = (data) => post('/chat/feedback', data)

// ---------------- 评测 ----------------
export const apiEvalDatasetPage = (params) => get('/eval/dataset/page', params)
export const apiEvalDatasetOptions = () => get('/eval/dataset/options')
export const apiEvalDatasetCreate = (data) => post('/eval/dataset', data)
export const apiEvalDatasetUpdate = (did, data) => put(`/eval/dataset/${did}`, data)
export const apiEvalDatasetDelete = (did) => del(`/eval/dataset/${did}`)
export const apiEvalCasePage = (params) => get('/eval/case/page', params)
export const apiEvalCaseCreate = (datasetId, data) => post('/eval/case', data, { params: { dataset_id: datasetId } })
export const apiEvalCaseBatch = (datasetId, data) => post('/eval/case/batch', data, { params: { dataset_id: datasetId } })
export const apiEvalCaseDelete = (cid) => del(`/eval/case/${cid}`)
export const apiEvalRunCreate = (data) => post('/eval/run', data)
export const apiEvalRunPage = (params) => get('/eval/run/page', params)
export const apiEvalRunItems = (runId) => get(`/eval/run/${runId}/items`)
export const apiEvalRunDelete = (runId) => del(`/eval/run/${runId}`)
export const apiEvalCompareCreate = (data) => post('/eval/compare', data)
export const apiEvalComparePage = (params) => get('/eval/compare/page', params)
export const apiEvalCompareDelete = (runId) => del(`/eval/compare/${runId}`)