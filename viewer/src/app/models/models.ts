

export interface Asset {
  id: bigint
  path: string
  uuid: string
  feature_id: bigint
  asset_type: string
}


export interface Project {
  description: string
  id: bigint
  name: string
  uuid: string
}
