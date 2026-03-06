import { StatCard } from '../../lib/types';

interface StatsRowProps {
    stats: StatCard[];
}

export function StatsRow({ stats }: StatsRowProps) {
    return (
        <div className="stats-row">
            {stats.map((s, i) => (
                <div key={i} className="stat-card">
                    <div className="stat-icon" style={{ background: s.bg }}>
                        <i className={`fas ${s.icon}`} style={{ color: s.ic }} />
                    </div>
                    <div>
                        <div className="stat-val">{s.val}</div>
                        <div className="stat-lbl">{s.lbl}</div>
                    </div>
                </div>
            ))}
        </div>
    );
}
