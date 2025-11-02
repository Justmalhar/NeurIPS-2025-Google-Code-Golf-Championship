def p(g):
 h,w=len(g),len(g[0]);d=(1,0,-1,0,1)
 for i in range(h):
  for j in range(w):
   if g[i][j]==5:
    S=[(i,j)];g[i][j]=10;R=[(i,j)]
    while S:
     x,y=S.pop()
     for k in range(4):
      u,v=x+d[k],y+d[k+1]
      if 0<=u<h and 0<=v<w and g[u][v]==5:g[u][v]=10;R+=((u,v),);S.append((u,v))
    q=5-len(R)
    for x,y in R:g[x][y]=q
 return g
