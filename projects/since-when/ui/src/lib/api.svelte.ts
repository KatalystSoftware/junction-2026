// The one way the app reaches the data service: JSON under /api on the same origin.

export const flags = $state({ fixture: false })

export class ApiError extends Error {
	status: number
	constructor(message: string, status: number) {
		super(message)
		this.status = status
	}
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
	const r = await fetch('/api' + path, init)
	const data = await r.json().catch(() => ({}))
	if (!r.ok) throw new ApiError(data.error || r.statusText, r.status)
	if (data.fixture === true) flags.fixture = true
	return data as T
}
