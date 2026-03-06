import { FlagItem } from '../../lib/types';

interface FlagsListProps {
    flags: FlagItem[];
}

export function FlagsList({ flags }: FlagsListProps) {
    return (
        <div className="flags-box">
            <div className="flags-title">
                <span><i className="fas fa-shield-halved" /> Integrity Alerts</span>
                <span style={{ background: '#334155', padding: '1px 7px', borderRadius: 10, fontSize: 9 }}>
                    {flags.length}
                </span>
            </div>

            {flags.length === 0 ? (
                <div className="flags-empty">
                    <i className="fas fa-shield-check"
                        style={{ display: 'block', fontSize: 20, marginBottom: 8, opacity: 0.4 }} />
                    No alerts yet
                </div>
            ) : (
                flags.map(f => (
                    <div key={f.id} className={`flag-item f-${f.type}`}>
                        <i className={`fas ${f.icon}`} style={{ flexShrink: 0, marginTop: 1 }} />
                        <div className="flag-txt">
                            {f.text}
                            <span className="flag-time">{f.time}</span>
                        </div>
                    </div>
                ))
            )}
        </div>
    );
}
