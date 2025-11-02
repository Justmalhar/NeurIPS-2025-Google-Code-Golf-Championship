E=enumerate
def p(m,*D):
	for A in(H:={*sum(m,[])}-{0}):C,I=zip(*[(B,D)for(B,C)in E(m)for(D,F)in E(C)if F==A]);D+=(max(C)-min(C)+1,A,min(C),min(I)),
	B,A,F,G=min(D);return[[(B==A)*sum(H,-A)for B in C[G:G+B:B//3]]for C in m[F:F+B:B//3]]