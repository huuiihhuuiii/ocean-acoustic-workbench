"""Configurable read-only agent loop with cancellation and visible tool evidence."""
import asyncio,json,inspect
async def run(request, messages, tools, execute, limit, stop, trace):
    rounds=0;seen={};reason=None
    while not stop.is_set():
        final=reason is not None
        if final:messages.append({'role':'user','content':'停止调用工具，根据已获取的证据整理答案，说明未完成项。停止原因：'+reason})
        task=asyncio.create_task(request(messages,[] if final else tools));cancel=asyncio.create_task(stop.wait())
        done,_=await asyncio.wait([task,cancel],return_when=asyncio.FIRST_COMPLETED)
        if cancel in done:
            task.cancel();await asyncio.gather(task,return_exceptions=True);return partial(trace,'用户已停止')
        cancel.cancel();await asyncio.gather(cancel,return_exceptions=True)
        try:result=await task
        except Exception as e:return partial(trace,'模型请求失败：'+str(e))
        rounds+=1;calls=result.get('tool_calls') or []
        if not calls:return result.get('content') or partial(trace,'模型没有返回答案')
        if final:return partial(trace,reason+'；模型仍要求工具，已停止')
        messages.append(result)
        for call in calls:
            args={}
            name=call.get('function',{}).get('name','');raw=call.get('function',{}).get('arguments','{}')
            try:
                args=json.loads(raw);key=name+json.dumps(args,sort_keys=True);seen[key]=seen.get(key,0)+1
                if seen[key]>=3:
                    reason='连续任务中同一工具和参数已请求3次';value={'error':reason}
                else:
                    value=execute(name,args)
                    if inspect.isawaitable(value):value=await value
            except Exception as e:value={'error':str(e)}
            trace.append({'round':rounds,'tool':name,'arguments':args if 'args' in locals() else {},'status':'error' if isinstance(value,dict) and bool(value.get('error')) else 'done'})
            messages.append({'role':'tool','tool_call_id':call['id'],'content':json.dumps(value,ensure_ascii=False)})
        if limit and rounds>=limit:reason='已达到自定义工具轮数 '+str(limit)
    return partial(trace,'用户已停止')
def partial(trace,reason):
    rows=[f"- 第 {r['round']} 轮：{r['tool']} {json.dumps(r['arguments'],ensure_ascii=False)}（{r['status']}）" for r in trace]
    return reason+'。当前未形成完整结论。已执行的工具记录：\n'+('\n'.join(rows) if rows else '尚未执行工具。')
