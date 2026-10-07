// IndexedDB 本地历史缓存（D11：刷新不丢历史）
// 服务端始终是权威源；本地缓存用于「打开会话先秒出历史」与「流式断流后仍能显示已到达内容」。
const DB_NAME = 'cloudloom'
const STORE = 'conv'

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1)
    req.onupgradeneeded = () => {
      const d = req.result
      if (!d.objectStoreNames.contains(STORE)) d.createObjectStore(STORE)
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

async function tx(mode: IDBTransactionMode, fn: (s: IDBObjectStore) => void): Promise<void> {
  try {
    const db = await openDb()
    await new Promise<void>((resolve, reject) => {
      const t = db.transaction(STORE, mode)
      fn(t.objectStore(STORE))
      t.oncomplete = () => resolve()
      t.onerror = () => reject(t.error)
      t.onabort = () => reject(t.error)
    })
    db.close()
  } catch { /* 隐私模式等场景静默降级，不影响主流程 */ }
}

export async function idbSave(convId: string, rows: unknown[]): Promise<void> {
  await tx('readwrite', (s) => s.put(rows, convId))
}

export async function idbLoad<T = any>(convId: string): Promise<T[]> {
  try {
    const db = await openDb()
    const v = await new Promise<any>((resolve, reject) => {
      const t = db.transaction(STORE, 'readonly')
      const r = t.objectStore(STORE).get(convId)
      r.onsuccess = () => resolve(r.result)
      r.onerror = () => reject(r.error)
    })
    db.close()
    return Array.isArray(v) ? (v as T[]) : []
  } catch { return [] }
}

export async function idbClear(convId: string): Promise<void> {
  await tx('readwrite', (s) => s.delete(convId))
}
