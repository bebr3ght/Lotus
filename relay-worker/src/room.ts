import { DurableObject } from 'cloudflare:workers';

/**
 * Rose Party Room - Durable Object
 *
 * Shared room where party members broadcast their skin selections.
 * All messages are JSON, broadcast to everyone else in the room.
 * Max 10 members per room.
 */

interface MemberInfo {
  summoner_id: number;
  summoner_name: string;
  skin?: SkinInfo;
}

interface SkinInfo {
  champion_id: number;
  skin_id: number;
  chroma_id?: number;
  skin_name?: string;
  champion_name?: string;
}

export class PartyRoom extends DurableObject {
  private static MAX_MEMBERS = 10;

  constructor(ctx: DurableObjectState, env: any) {
    super(ctx, env);
    this.ctx.setWebSocketAutoResponse(
      new WebSocketRequestResponsePair('ping', 'pong'),
    );
  }

  async fetch(request: Request): Promise<Response> {
    const sockets = this.ctx.getWebSockets();
    const active = sockets.filter(ws => ws.readyState === WebSocket.READY_STATE_OPEN);

    if (active.length >= PartyRoom.MAX_MEMBERS) {
      return new Response('Room is full', { status: 409 });
    }

    const pair = new WebSocketPair();
    const [client, server] = Object.values(pair);

    this.ctx.acceptWebSocket(server);

    // Send current member list to the new joiner
    const members = this.getMembers();
    server.send(JSON.stringify({ type: 'members', members }));

    return new Response(null, { status: 101, webSocket: client });
  }

  async webSocketMessage(ws: WebSocket, message: string | ArrayBuffer) {
    if (typeof message !== 'string') return;
    if (message === 'pong') return;

    let msg: any;
    try {
      msg = JSON.parse(message);
    } catch {
      return;
    }

    switch (msg.type) {
      case 'join': {
        // Member announces themselves
        const info: MemberInfo = {
          summoner_id: msg.summoner_id,
          summoner_name: msg.summoner_name || 'Unknown',
        };
        ws.serializeAttachment(info);
        this.broadcastMembers();
        break;
      }
      case 'skin': {
        // Member updated their skin selection
        const existing = ws.deserializeAttachment() as MemberInfo | null;
        if (existing) {
          existing.skin = msg.skin || null;
          ws.serializeAttachment(existing);
          this.broadcastMembers();
        }
        break;
      }
      case 'leave': {
        ws.close(1000, 'client left');
        break;
      }
    }
  }

  async webSocketClose(ws: WebSocket) {
    // Clear the member info so getMembers() won't include them
    ws.serializeAttachment(null);
    this.broadcastMembers();
  }

  async webSocketError(ws: WebSocket) {
    ws.serializeAttachment(null);
    this.broadcastMembers();
  }

  private getMembers(): MemberInfo[] {
    const members: MemberInfo[] = [];
    for (const ws of this.ctx.getWebSockets()) {
      try {
        if (ws.readyState !== WebSocket.READY_STATE_OPEN) continue;
        const info = ws.deserializeAttachment() as MemberInfo | null;
        if (info?.summoner_id) {
          members.push(info);
        }
      } catch {}
    }
    return members;
  }

  private broadcastMembers() {
    const members = this.getMembers();
    const payload = JSON.stringify({ type: 'members', members });
    for (const ws of this.ctx.getWebSockets()) {
      try {
        if (ws.readyState === WebSocket.READY_STATE_OPEN) {
          ws.send(payload);
        }
      } catch {}
    }
  }
}
