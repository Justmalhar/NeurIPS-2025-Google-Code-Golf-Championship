def p(g):
 h,w=len(g),len(g[0]);d=1,0,-1,0,1
 b=max(range(10),key=sum(g,[]).count)
 for i in range(h):
  for j in range(w):
   x=g[i][j]
   if x!=b and x-10:
    t=x;S=[(i,j)];R=[(i,j)];g[i][j]=10
    while S:
     x,y=S.pop()
     for k in range(4):
      u,v=x+d[k],y+d[k+1]
      if 0<=u<h and 0<=v<w and g[u][v]==t:g[u][v]=10;S+=[(u,v)];R+=[(u,v)]
    for x,y in R:g[x][y]=(len(R)==6)+1
 return g