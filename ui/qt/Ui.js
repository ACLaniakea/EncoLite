.pragma library
function options(rows, valueKey, labelKey) {
    return (rows || []).map(function(row) { return {value:row[valueKey || 'id'],label:row[labelKey || 'name']}; });
}
function indexed(rows) { return (rows || []).map(function(name,index) { return {value:index,label:name}; }); }
function details(s) {
    var transparent = s.noise === 'transparency' || s.noise === 'vocal';
    var rows = (s.noise_options || []).filter(function(row) {
        return transparent ? ['transparency','vocal'].indexOf(row.key)>=0 : ['off','transparency','vocal'].indexOf(row.key)<0;
    });
    return {title:transparent?'通透模式':'降噪强度', options:options(rows,'key'),
            current:transparent?s.noise:s.anc_level,
            visible:!!s.connected && !!s.noise && s.noise!=='off' && rows.length>1,
            enabled:transparent?!!s.can_transparency:!!s.can_anc};
}
function noise(s, mode) {
    if (mode!=='anc') return mode;
    var rows=(s.noise_options||[]).filter(function(row){return ['off','transparency','vocal'].indexOf(row.key)<0;});
    return rows.some(function(row){return row.key===s.anc_level;})?s.anc_level:rows.length?rows[0].key:'smart';
}
function ticks(minimum, maximum) {
    var values=[maximum,minimum],step=maximum-minimum<=12?3:maximum-minimum<=24?6:12;
    for(var v=Math.ceil(minimum/step)*step;v<maximum;v+=step)if(values.indexOf(v)<0)values.push(v);
    return values.sort(function(a,b){return b-a;});
}
function gain(value) { return (value>0?'+':'')+Math.round(value); }
