def p(g):
 h=eval(str(g))
 for x in range(729):
  i,j,a,b=x//81,x//9%9,x%9//3-1,x%3-1;v=h[i][j]
  if a*a+b*b==v>0:g[i+a][j+b]=10-3*v
 return g