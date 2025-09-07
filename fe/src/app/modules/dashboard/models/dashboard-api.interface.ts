export type DashBoardData = {
  id: number,
  anomaly_count: number,
  anomaly_verified: number,
  meter_data: {
    id: number,
    name: string,
    address: string,
    status: number
  }
}

export enum Status {
  NORMAL = 0,
  ANOMALY = 1,
  LOST_CONNECTION = 2
}
