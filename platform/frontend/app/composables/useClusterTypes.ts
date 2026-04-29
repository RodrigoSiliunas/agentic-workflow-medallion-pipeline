/**
 * Catalogo curado de cluster node types disponiveis no wizard advanced.
 *
 * Pricing baseado em AWS us-east-2 + Databricks Premium tier (Jobs Compute):
 *   total_cost/h = (instance_price * num_nodes) + (dbu_per_hour * num_nodes * dbu_rate)
 *
 * DBU rate Premium Jobs Compute = $0.15/DBU (atualizar se Databricks mudar)
 * EC2 prices = on-demand AWS us-east-2 (snapshot 2026-04)
 *
 * NAO buscar via API real — Databricks nao expoe catalog publico estavel.
 * Curated list eh suficiente pra UI; usuario digita node_type custom via env_var
 * se precisar tipo nao listado.
 */

export interface ClusterType {
  /** AWS instance type id (vai pro Databricks API node_type_id) */
  id: string
  /** Label curto na UI (Micro/Small/Medium/Large) */
  label: string
  /** Categoria visual (micro/general/memory/compute/storage) */
  category: "micro" | "general" | "memory" | "compute" | "storage"
  /** RAM em GB */
  ramGb: number
  /** vCPU cores */
  vcpu: number
  /** Local SSD em GB (0 se EBS-only) */
  localSsdGb: number
  /** EC2 on-demand $/h em us-east-2 */
  instancePricePerHr: number
  /** DBU consumption per hour (Databricks unit) */
  dbuPerHr: number
  /** Use case suggestion */
  useCase: string
  /** Warning text — mostrado se tier tem caveat (ex: micro burstable). */
  warning?: string
}

const DBU_RATE_USD = 0.15 // Premium Jobs Compute

export const CLUSTER_TYPES: ClusterType[] = [
  {
    id: "m5.large",
    label: "Eco",
    category: "micro",
    ramGb: 8,
    vcpu: 2,
    localSsdGb: 0,
    instancePricePerHr: 0.096,
    dbuPerHr: 0.75,
    useCase: "Smallest viavel Databricks, sem SSD (shuffle via EBS — mais lento)",
    warning: "Sem local SSD — shuffle/cache vai pra EBS, ~30% mais lento que Small em JOINs grandes.",
  },
  {
    id: "m5d.large",
    label: "Small",
    category: "general",
    ramGb: 8,
    vcpu: 2,
    localSsdGb: 75,
    instancePricePerHr: 0.113,
    dbuPerHr: 0.75,
    useCase: "Dev/teste, pipelines pequenos (<1GB/run)",
  },
  {
    id: "m5d.xlarge",
    label: "Medium",
    category: "general",
    ramGb: 16,
    vcpu: 4,
    localSsdGb: 150,
    instancePricePerHr: 0.226,
    dbuPerHr: 1.5,
    useCase: "Pipelines pequenos a medios (1-10GB/run)",
  },
  {
    id: "m5d.2xlarge",
    label: "Large",
    category: "general",
    ramGb: 32,
    vcpu: 8,
    localSsdGb: 300,
    instancePricePerHr: 0.452,
    dbuPerHr: 3.0,
    useCase: "Pipelines medios (10-50GB/run)",
  },
  {
    id: "m5d.4xlarge",
    label: "XLarge",
    category: "general",
    ramGb: 64,
    vcpu: 16,
    localSsdGb: 600,
    instancePricePerHr: 0.904,
    dbuPerHr: 6.0,
    useCase: "Pipelines grandes (50-200GB/run)",
  },
  {
    id: "r5d.2xlarge",
    label: "Memory",
    category: "memory",
    ramGb: 64,
    vcpu: 8,
    localSsdGb: 300,
    instancePricePerHr: 0.576,
    dbuPerHr: 4.0,
    useCase: "Joins/aggregations pesados (RAM-bound)",
  },
  {
    id: "i3.xlarge",
    label: "Storage",
    category: "storage",
    ramGb: 30.5,
    vcpu: 4,
    localSsdGb: 950,
    instancePricePerHr: 0.312,
    dbuPerHr: 1.0,
    useCase: "Cache local SSD intensivo, shuffle pesado",
  },
  {
    id: "c5.2xlarge",
    label: "Compute",
    category: "compute",
    ramGb: 16,
    vcpu: 8,
    localSsdGb: 0,
    instancePricePerHr: 0.34,
    dbuPerHr: 2.0,
    useCase: "CPU-bound (regex/parse/transform sem JOIN)",
  },
]

export const SPARK_VERSIONS = [
  { id: "15.4.x-scala2.12", label: "15.4 LTS (recomendado)" },
  { id: "14.3.x-scala2.12", label: "14.3 LTS" },
  { id: "13.3.x-scala2.12", label: "13.3 LTS" },
  { id: "16.1.x-scala2.12", label: "16.1 (latest, nao LTS)" },
]

export interface CostEstimateInput {
  driver: ClusterType
  worker: ClusterType
  /** Modo Fixo: numero de workers. Ignorado se autoscale set. */
  numWorkers?: number
  /** Modo autoscale: min workers. */
  autoscaleMin?: number
  /** Modo autoscale: max workers. */
  autoscaleMax?: number
}

export interface CostEstimateOutput {
  ec2MaxPerHr: number
  dbuMaxPerHr: number
  totalMaxPerHr: number
  /** So preenchido em autoscale: medio (min+max)/2 estimado. */
  totalAvgPerHr?: number
  totalDbuMax: number
}

export function useClusterTypes() {
  return {
    clusterTypes: CLUSTER_TYPES,
    sparkVersions: SPARK_VERSIONS,
    dbuRate: DBU_RATE_USD,
    /** Calcula custo estimado por hora — driver + workers + autoscale-aware. */
    estimateHourlyCost(input: CostEstimateInput): CostEstimateOutput {
      const isAutoscale = input.autoscaleMin != null && input.autoscaleMax != null
      const maxWorkers = isAutoscale ? input.autoscaleMax! : (input.numWorkers ?? 0)
      const minWorkers = isAutoscale ? input.autoscaleMin! : (input.numWorkers ?? 0)

      const driverEc2 = input.driver.instancePricePerHr
      const driverDbu = input.driver.dbuPerHr
      const workerEc2 = input.worker.instancePricePerHr * maxWorkers
      const workerDbu = input.worker.dbuPerHr * maxWorkers
      const ec2Max = driverEc2 + workerEc2
      const dbuMax = driverDbu + workerDbu
      const totalMax = ec2Max + dbuMax * DBU_RATE_USD
      let totalAvg: number | undefined
      if (isAutoscale) {
        const avgWorkers = (minWorkers + maxWorkers) / 2
        const avgEc2 = driverEc2 + input.worker.instancePricePerHr * avgWorkers
        const avgDbu = driverDbu + input.worker.dbuPerHr * avgWorkers
        totalAvg = avgEc2 + avgDbu * DBU_RATE_USD
      }
      return {
        ec2MaxPerHr: ec2Max,
        dbuMaxPerHr: dbuMax * DBU_RATE_USD,
        totalMaxPerHr: totalMax,
        totalAvgPerHr: totalAvg,
        totalDbuMax: dbuMax,
      }
    },
    /** Custo formatado USD/h tipo "$0.85/h" */
    formatCost(value: number): string {
      return `$${value.toFixed(2)}/h`
    },
    findById(id: string): ClusterType | undefined {
      return CLUSTER_TYPES.find((t) => t.id === id)
    },
  }
}
