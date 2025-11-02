def p(g):
	*g,=zip(*g)
	for D in sum(g,()):
		A=[A for(A,B)in enumerate(g)if D in B]
		if A[-1]-A[0]==6:
			for E in A:B=g[E];C=20-B[::-1].index(D);g[E]=B[:C]+(max(B[C:]),)*(20-C)
	return[*zip(*g)]